"""GitChameleon 2.0 runner: generate (cached, resumable) -> score (docker) -> report.

    python harness/gc_runner.py run       --provider openai --model gpt-4.1-mini --ids dev   # A1 greedy
    python harness/gc_runner.py selfdebug --provider openai --model gpt-4.1-mini --ids dev   # A3, needs A1 first
    python harness/gc_runner.py generate|score ...                                           # A1 halves

Stdlib only. Every model response is stored in data/cache/generations.sqlite, keyed by the
full request, so re-running never pays twice and an interrupted run resumes.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import hashlib
import json
import math
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "external/GitChameleonBenchmark/dataset/dataset.jsonl"
SUBSET = ROOT / "harness/dev_subset_ids.json"
CACHE = ROOT / "data/cache/generations.sqlite"
RUNS = ROOT / "data/cache/runs"
IMAGE = "mrcabbage972/gitchameleon:latest"
VOLUME = "gc_venvs"

PROVIDERS = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
}

# Paper Fig. 17(a) zero-shot system prompt and 17(c) user prompt (numbering quirk kept).
SYSTEM_PROMPT = """You are a skilled Python programmer tasked with solving a coding problem. Your goal is to provide a clear, efficient, and correct solution that meets all the specified requirements.

Please provide your solution following these guidelines:
1. Use the required library in your solution.
2. Incorporate the provided starter code correctly.
3. Write your solution in Python.
4. Format your solution within a markdown code block.
5. Ensure your code is clean, efficient, and well-commented.
6. Output only the code block and nothing else.

Example output format:
```python
# [Your code here, incorporating the starter code]

# [Additional code and comments as needed]
```

After writing your solution, please review it to ensure all requirements are met and the code is correct and efficient.

Here are the key elements for this task:"""

USER_TEMPLATE = """1. Required Library:
<library>
{library}
</library>

2. Python version:
<python>
{python_version}
</python>

2. Coding Problem:
<coding_problem>
{problem}
</coding_problem>

3. Starter Code:
<starter_code>
{starting_code}
</starter_code>"""

# Paper Fig. 18 self-debug prompts. NOTE: the text of Sec. 3.1.3 says the model's own
# explanation is also fed back, but the figure's user prompt has no such field; we follow the figure.
SD_SYSTEM_PROMPT = """You are an expert programming assistant. Your task is to fix issues in a generated Python solution for a given programming problem. You are provided with:
- A problem statement
- Starter code
- A previously generated incorrect solution
- A top-level execution trace or error message
- Dependencies information (versions, libraries).

Please generate a corrected Python solution by following these strict guidelines:
1. Use the required libraries explicitly in your code.
2. Correctly incorporate the provided starter code - do not remove or alter its structure.
3. Write in standard Python syntax.
4. Wrap your entire solution within a single Markdown code block.
5. Do not include any text outside the code block - no explanations, comments, docstrings, or usage examples.
6. Ensure the code is clean, efficient, and syntactically valid.
7. Avoid interactive, stateful, or environment-dependent constructs (e.g., Django projects, web servers).
8. Your output must be executable in a non-interactive environment (e.g., a test harness or script runner).

Example output format:

```python
# [Your corrected code here]
```

Before submitting, carefully review your code for correctness, completeness, and adherence to all constraints."""

SD_USER_TEMPLATE = """<Problem>
{problem}
</Problem>

<Python Version>
{python_version}
</Python Version>

<Library>
{library}
</Library>

<Version>
{version}
</Version>

<Extra Dependencies>
{additional_dependencies}
</Extra Dependencies>

<Starting Code>
{starting_code}
</Starting Code>

<Generated Solution>
{solution}
</Generated Solution>

<Trace>
{trace}
</Trace>"""

ANSWER_SCHEMA = {
    "name": "answer",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {"Answer": {"type": "string"}, "Explanation": {"type": "string"}},
        "required": ["Answer", "Explanation"],
        "additionalProperties": False,
    },
}


# ---------------------------------------------------------------- data

def load_dataset() -> list[dict]:
    return [json.loads(l) for l in DATASET.read_text(encoding="utf8").splitlines() if l.strip()]


def select_ids(spec: str, rows: list[dict]) -> list[int]:
    if spec == "dev":
        return json.loads(SUBSET.read_text())["example_ids"]
    if spec == "all":
        return sorted(int(r["example_id"]) for r in rows)
    return [int(x) for x in spec.split(",")]


def render_user(row: dict, library_fmt: str = "pinned") -> str:
    # ASSUMPTION: the paper states the version is in the prompt but Fig. 17(c) only shows a
    # `library` tag, so by default it is rendered as "name==version". Verify against A1.
    lib = f"{row['library']}=={row['version']}" if library_fmt == "pinned" else row["library"]
    return USER_TEMPLATE.format(
        library=lib, python_version=row["python_version"], problem=row["problem"],
        starting_code=row["starting_code"])


def render_sd_user(row: dict, solution: str, trace: str, show_test: bool = False) -> str:
    text = SD_USER_TEMPLATE.format(
        problem=row["problem"], python_version=row["python_version"], library=row["library"],
        version=row["version"], additional_dependencies=row.get("additional_dependencies") or "",
        starting_code=row["starting_code"], solution=solution, trace=trace)
    if show_test:  # variant, not in the paper's Fig. 18: the visible test is shown to the model by design
        text += "\n\n<Visible Test>\n" + row["test"] + "\n</Visible Test>"
    return text


def venv_name(row: dict) -> str:
    key = "-".join([row["python_version"], row["library"], row["version"], row.get("additional_dependencies", "")])
    return "gcham_venv_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- cache

def open_cache() -> sqlite3.Connection:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(CACHE)
    db.execute("""CREATE TABLE IF NOT EXISTS gens (
        key TEXT PRIMARY KEY, provider TEXT, model TEXT, arm TEXT, example_id INTEGER, seed INTEGER,
        request TEXT, raw TEXT, answer TEXT, prompt_tokens INTEGER, completion_tokens INTEGER,
        latency_s REAL, created_at REAL)""")
    return db


def request_body(model: str, system: str, user: str, temperature: float, top_p: float,
                 structured: bool, seed: int | None) -> dict:
    body = {"model": model, "temperature": temperature, "top_p": top_p,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if structured:
        body["response_format"] = {"type": "json_schema", "json_schema": ANSWER_SCHEMA}
    if seed:
        body["seed"] = seed
    return body


def cache_key(provider: str, arm: str, example_id: int, seed: int, body: dict) -> str:
    blob = json.dumps([provider, arm, example_id, seed, body], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


# ---------------------------------------------------------------- api

def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip().upper()] = v.strip().strip('"').strip("'")
    env.update({k.upper(): v for k, v in os.environ.items() if k.upper().endswith("_API_KEY")})
    return env


def call_api(base: str, key: str, body: dict, retries: int = 6, path: str = "/chat/completions") -> dict:
    data = json.dumps(body).encode()
    for attempt in range(retries):
        req = urllib.request.Request(base + path, data=data, headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json",
            "User-Agent": "pinpoint-harness/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(min(60, 2 ** attempt * 2))
                continue
            raise RuntimeError(f"HTTP {e.code}: {detail}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def extract_answer(raw: str, structured: bool) -> str:
    if structured:
        try:
            return json.loads(raw)["Answer"]
        except (ValueError, KeyError, TypeError):
            pass
    return raw


# ---------------------------------------------------------------- generate

def run_requests(args, arm: str, requests: list[tuple[int, dict]], structured: bool) -> None:
    """Send every (example_id, body) not already cached; store results; skip failures (retried next run)."""
    base, key_name = PROVIDERS[args.provider]
    api_key = load_env().get(key_name)
    if not api_key:
        sys.exit(f"{key_name} not found in .env or environment")
    db = open_cache()
    todo = []
    for i, body in requests:
        k = cache_key(args.provider, arm, i, args.seed, body)
        if db.execute("SELECT 1 FROM gens WHERE key=?", (k,)).fetchone() is None:
            todo.append((i, k, body))
    print(f"[{arm}] {len(requests)} requests, {len(requests) - len(todo)} cached, {len(todo)} to generate")

    def work(item):
        i, k, body = item
        t0 = time.time()
        return i, k, body, call_api(base, api_key, body), time.time() - t0

    done = tok_in = tok_out = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for f in cf.as_completed([pool.submit(work, it) for it in todo]):
            try:
                i, k, body, resp, dt = f.result()
            except Exception as e:
                print("  failed:", str(e)[:200])
                continue
            raw = resp["choices"][0]["message"].get("content") or ""
            usage = resp.get("usage", {})
            db.execute("INSERT OR REPLACE INTO gens VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                k, args.provider, args.model, arm, i, args.seed, json.dumps(body), raw,
                extract_answer(raw, structured), usage.get("prompt_tokens"),
                usage.get("completion_tokens"), dt, time.time()))
            db.commit()
            done += 1
            tok_in += usage.get("prompt_tokens") or 0
            tok_out += usage.get("completion_tokens") or 0
    print(f"[{arm}] generated {done}/{len(todo)}; tokens in={tok_in} out={tok_out}")


def cached_answer(args, arm: str, i: int, body: dict) -> str | None:
    hit = open_cache().execute("SELECT answer FROM gens WHERE key=?",
                               (cache_key(args.provider, arm, i, args.seed, body),)).fetchone()
    return None if hit is None else hit[0]


def a1_body(args, row: dict) -> dict:
    return request_body(args.model, SYSTEM_PROMPT, render_user(row, args.library_fmt),
                        args.temperature, args.top_p, not args.no_structured, args.seed or None)


def generate(args, ids: list[int]) -> None:
    by_id = {int(r["example_id"]): r for r in load_dataset()}
    run_requests(args, "A1", [(i, a1_body(args, by_id[i])) for i in ids], not args.no_structured)


# ---------------------------------------------------------------- score

def run_dir(args, arm: str) -> Path:
    ids = args.ids if args.ids in ("dev", "all") else "custom"
    return RUNS / f"{args.provider}_{args.model.replace('/', '-')}_{arm}_s{args.seed}_{ids}"


def write_solutions(out: Path, answers: dict[int, str]) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / "solutions.jsonl"
    with path.open("w", encoding="utf8") as f:
        for i, a in sorted(answers.items()):
            f.write(json.dumps({"example_id": str(i), "answer": a}) + "\n")
    return path


def docker_run(extra_mounts: list[str], cmd: str, timeout: int) -> subprocess.CompletedProcess:
    argv = ["docker", "run", "--rm", "-v", f"{VOLUME}:/app/.dataset_venvs"]
    for m in extra_mounts:
        argv += ["-v", m]
    argv += [IMAGE, "-c", cmd]
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)


def score_solutions(args, sol: Path, ids: list[int]) -> Path:
    rows = {int(r["example_id"]): r for r in load_dataset()}
    have = set(docker_run([], "ls /app/.dataset_venvs", 120).stdout.split())
    absent = [i for i in ids if venv_name(rows[i]) not in have]
    if absent:
        sys.exit(f"{len(absent)} problems have no built environment (would be scored as false failures): {absent}")
    res = docker_run([f"{sol.parent}:/work"],
                     "pyenv global 3.9 && poetry run python gitchameleon/run_eval.py --dataset_file dataset.jsonl "
                     f"--solution_file /work/solutions.jsonl --env_dir .dataset_venvs --test_dir hidden_tests "
                     f"--workers {args.score_workers}", 6 * 3600)
    if res.returncode != 0:
        sys.exit("scoring failed:\n" + res.stdout[-1500:] + res.stderr[-1500:])
    return sol.parent / "solutions_eval_results.csv"


def read_results(csv_path: Path) -> list[dict]:
    with csv_path.open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(f))


def score_a1(args, ids: list[int]) -> Path:
    by_id = {int(r["example_id"]): r for r in load_dataset()}
    answers, missing = {}, []
    for i in ids:
        a = cached_answer(args, "A1", i, a1_body(args, by_id[i]))
        (missing.append(i) if a is None else answers.__setitem__(i, a))
    if missing:
        print(f"WARNING: {len(missing)} problems have no generation and are left out: {missing}")
    return score_solutions(args, write_solutions(run_dir(args, "A1"), answers), sorted(answers))


def selfdebug(args, ids: list[int]) -> Path:
    """Self-debug. Default = A3 as published (one round, only for problems whose A1 answer failed the
    VISIBLE test; the model sees its previous code and the visible-test trace; the rest keep their A1 answer).
    Variants: --rounds N repeats on whatever still fails the visible test; --show-test adds the visible
    test source to the prompt. Hidden tests are never used inside the loop."""
    by_id = {int(r["example_id"]): r for r in load_dataset()}
    a1_dir = run_dir(args, "A1")
    a1_csv = a1_dir / "solutions_eval_results.csv"
    if not a1_csv.exists():
        sys.exit(f"run A1 first (missing {a1_csv})")
    state = {int(r["example_id"]): r for r in read_results(a1_csv)}
    answers = {int(json.loads(l)["example_id"]): json.loads(l)["answer"]
               for l in (a1_dir / "solutions.jsonl").read_text(encoding="utf8").splitlines()}
    ids = [i for i in ids if i in state]
    label = "A3" + ("t" if args.show_test else "") + (f"r{args.rounds}" if args.rounds > 1 else "")
    for rnd in range(1, args.rounds + 1):
        failed = [i for i in ids if state[i]["passed_manual"] != "True"]
        print(f"[{label}] round {rnd}: {len(failed)}/{len(ids)} problems still fail the visible test")
        if not failed:
            break
        arm = "A3" + ("t" if args.show_test else "") + ("" if rnd == 1 else f"_r{rnd}")
        reqs = [(i, request_body(args.model, SD_SYSTEM_PROMPT,
                                 render_sd_user(by_id[i], answers[i], state[i]["output_manual"], args.show_test),
                                 args.temperature, args.top_p, False, args.seed or None)) for i in failed]
        run_requests(args, arm, reqs, False)
        for i, body in reqs:
            a = cached_answer(args, arm, i, body)
            if a is not None:
                answers[i] = a
        if rnd < args.rounds:  # need fresh visible-test feedback for the next round
            scratch = write_solutions(run_dir(args, f"{label}_scratch{rnd}"), {i: answers[i] for i in failed})
            state.update({int(r["example_id"]): r for r in read_results(score_solutions(args, scratch, failed))})
    return score_solutions(args, write_solutions(run_dir(args, label), {i: answers[i] for i in ids}), ids)


def rag(args, ids: list[int]) -> Path:
    """A2: docs-RAG. Top-k chunks (text-embedding-3-large, cosine) from the problem's own `docs` pages,
    appended to the A1 user prompt. Problems whose pages all failed to load get the plain A1 prompt."""
    import gc_docs as d
    by_id = {int(r["example_id"]): r for r in load_dataset()}
    key, base = load_env()[PROVIDERS["openai"][1]], PROVIDERS["openai"][0]
    corpus = d.build_corpus()
    texts = [c for i in ids for u in by_id[i]["docs"] for c in d.chunks(corpus[u]["text"])]
    queries = [by_id[i]["problem"] for i in ids]
    vecs = d.embed(sorted(set(texts + queries)), key, base)
    arm, reqs, no_docs = f"A2k{args.rag_k}", [], []
    for i in ids:
        row = by_id[i]
        top = d.retrieve(row, corpus, vecs, vecs[d._ekey(row["problem"])], args.rag_k)
        user = render_user(row, args.library_fmt)
        if top:
            user += "\n\n5. Documentation:\n<documentation>\n" + "\n\n---\n\n".join(top) + "\n</documentation>"
        else:
            no_docs.append(i)
        reqs.append((i, request_body(args.model, SYSTEM_PROMPT, user, args.temperature, args.top_p,
                                     not args.no_structured, args.seed or None)))
    print(f"[{arm}] {len(no_docs)} problems have no retrievable docs: {no_docs}")
    run_requests(args, arm, reqs, not args.no_structured)
    answers = {i: a for i, b in reqs if (a := cached_answer(args, arm, i, b)) is not None}
    (RUNS / "no_docs_ids.json").parent.mkdir(parents=True, exist_ok=True)
    (RUNS / "no_docs_ids.json").write_text(json.dumps(no_docs))
    return score_solutions(args, write_solutions(run_dir(args, arm), answers), sorted(answers))


def report(csv_path: Path, rows_by_id: dict[int, dict]) -> None:
    res = read_results(csv_path)
    n = len(res)

    def rate(key, subset):
        k = sum(r[key] == "True" for r in subset)
        p = k / len(subset)
        return k, p, 1.96 * math.sqrt(p * (1 - p) / len(subset))

    ps = {}
    for label, key in (("hidden", "passed"), ("visible", "passed_manual")):
        k, p, ci = rate(key, res)
        ps[label] = p
        print(f"{label:8s} {k}/{n} = {100 * p:.1f}%  (95% CI +/-{100 * ci:.1f})")
    print(f"visible-hidden gap: {100 * (ps['visible'] - ps['hidden']):.1f} pts")
    by = {}
    for r in res:
        t = rows_by_id[int(r["example_id"])]["type_of_change"].lower()
        c = ("argument/attribute" if "argument" in t or "attribute" in t else "name" if "name" in t
             else "deprecation" if "deprecat" in t else "new feature/func" if "new" in t else "other")
        by.setdefault(c, []).append(r)
    for c, sub in sorted(by.items()):
        k, p, _ = rate("passed", sub)
        print(f"  hidden by class  {c:20s} {k}/{len(sub)} = {100 * p:.0f}%")


# ---------------------------------------------------------------- cli

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["generate", "score", "run", "selfdebug", "rag"])
    ap.add_argument("--provider", choices=sorted(PROVIDERS), default="openai")
    ap.add_argument("--model", required=True)
    ap.add_argument("--ids", default="dev", help="dev | all | comma-separated example ids")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--top-p", dest="top_p", type=float, default=0.95)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--score-workers", type=int, default=2, help="keep low: ~3.8 GB RAM is available to Docker here")
    ap.add_argument("--no-structured", action="store_true", help="skip the Answer/Explanation JSON schema (A1)")
    ap.add_argument("--rounds", type=int, default=1, help="self-debug rounds (paper-faithful default: 1)")
    ap.add_argument("--show-test", action="store_true", help="self-debug variant: add the visible test source")
    ap.add_argument("--rag-k", type=int, default=3, help="A2: number of retrieved doc chunks (paper: 1 and 3)")
    ap.add_argument("--library-fmt", choices=["pinned", "name"], default="pinned")
    args = ap.parse_args()

    rows = load_dataset()
    ids = select_ids(args.ids, rows)
    by_id = {int(r["example_id"]): r for r in rows}
    if args.cmd in ("generate", "run"):
        generate(args, ids)
    csv_path = None
    if args.cmd in ("score", "run"):
        csv_path = score_a1(args, ids)
    if args.cmd == "selfdebug":
        csv_path = selfdebug(args, ids)
    if args.cmd == "rag":
        csv_path = rag(args, ids)
    if csv_path:
        report(csv_path, by_id)


if __name__ == "__main__":
    main()
