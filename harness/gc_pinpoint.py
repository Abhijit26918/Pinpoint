"""PinPoint arms on GitChameleon: introspect the pinned library, diff the code, repair, repeat.

  A4 = PinPoint on top of the A1 answers      (--base A1)
  A5 = PinPoint on top of the A3 self-debug   (--base A3)

Per turn: resolve the library calls in each current answer -> probe them INSIDE that problem's pinned
venv (one container per turn) -> diff -> for problems with a verified error, ask the model to fix just
those, quoting what the installed package really exposes. Stops early for a problem once its diff is
clean. DEPRECATED findings are informational and never trigger a repair (the benchmark's own correct
solutions use deprecated APIs). Hidden tests are never used inside the loop; only the final scoring does.

Usage: python harness/gc_pinpoint.py repair --model gpt-4.1-mini --ids dev --base A1 --turns 3
"""
import argparse
import collections
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "src"))
import gc_runner as g  # noqa: E402
from pinpoint.diff import Issue, diff, paths_to_probe  # noqa: E402
from pinpoint.resolve import resolve  # noqa: E402

WORK = ROOT / "data/cache/pinpoint_probe"
FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.S)

PP_SYSTEM_PROMPT = """You are an expert programming assistant. Your task is to fix version-compatibility errors in a generated Python solution. You are provided with:
- A problem statement and starter code
- The exact Python and library versions that will run the code
- A previously generated solution
- Findings obtained by inspecting the INSTALLED library (not documentation): these are facts about what exists in that exact version

Fix every finding with the smallest change that keeps the solution's behaviour. Follow these rules:
1. Use only names, modules and arguments that the findings show exist in the installed version.
2. Correctly incorporate the starter code - do not remove or alter its structure.
3. Wrap your entire solution within a single Markdown code block.
4. Do not include any text outside the code block.
5. The code must run in a non-interactive environment.

Example output format:

```python
# [Your corrected code here]
```"""

PP_USER_TEMPLATE = """<Problem>
{problem}
</Problem>

<Python Version>
{python_version}
</Python Version>

<Library>
{library}=={version}
</Library>

<Extra Dependencies>
{additional_dependencies}
</Extra Dependencies>

<Starting Code>
{starting_code}
</Starting Code>

<Generated Solution>
{solution}
</Generated Solution>

<Findings from the installed library>
{findings}
</Findings from the installed library>"""


def code_of(answer: str) -> str:
    """Code of a model answer: first fenced block, else the text itself (matches the scorer's extraction)."""
    m = FENCE.search(answer)
    return m.group(1) if m else answer


def _members(x: Issue) -> str:
    """What the installed parent really exposes, so a missing name can be replaced by one that exists."""
    if not x.siblings:
        return ""
    parent = x.path.rsplit(".", 1)[0]
    items = ", ".join(f"{m['name']}{m['signature'] or ''}" if m["kind"] in ("function", "class") else m["name"]
                      for m in x.siblings)
    return f" The installed `{parent}` provides: {items}."


def render_findings(issues: list[Issue]) -> str:
    lines = []
    for n, x in enumerate(issues, 1):
        if x.kind == "SIGNATURE":
            lines.append(f"{n}. line {x.line}: call to `{x.path}`: {x.detail}. The installed signature is `{x.path.rsplit('.', 1)[-1]}{x.signature}`.")
        elif x.kind in ("RENAMED", "MOVED"):
            where = "Names that do exist nearby" if x.kind == "RENAMED" else "It is defined in"
            lines.append(f"{n}. line {x.line}: `{x.path}` does not exist in the installed version ({x.detail}). {where}: " + ", ".join(f"`{s}`" for s in x.suggestions) + "." + _members(x))
        else:  # MISSING
            lines.append(f"{n}. line {x.line}: `{x.path}` does not exist in the installed version ({x.detail}); no similarly named symbol was found, so use a different approach." + _members(x))
    return "\n".join(lines)


def probe_envs(by_env: dict[str, list[str]]) -> dict[str, dict[str, dict]]:
    """Probe dotted paths inside each pinned venv (one container for all). Returns env -> path -> result."""
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    shutil.copy(ROOT / "src/pinpoint/probe.py", WORK / "probe.py")
    envs = sorted(e for e, p in by_env.items() if p)
    for e in envs:
        (WORK / f"req_{e}.json").write_text(json.dumps({"paths": sorted(set(by_env[e]))}))
    if not envs:
        return {}
    script = "; ".join(
        f"timeout 600 /app/.dataset_venvs/{e}/bin/python -I /work/probe.py < /work/req_{e}.json > /work/out_{e}.json 2> /work/err_{e}.txt"
        for e in envs)
    g.docker_run([f"{WORK}:/work"], script, 4 * 3600)
    out = {}
    for e in envs:
        f = WORK / f"out_{e}.json"
        if f.exists() and f.stat().st_size:
            paths = json.loads((WORK / f"req_{e}.json").read_text())["paths"]
            out[e] = dict(zip(paths, json.loads(f.read_text())["results"]))
    return out


def find_issues(answers: dict[int, str], by_id: dict[int, dict]) -> dict[int, list[Issue]]:
    uses = {i: [u for u in resolve(code_of(a)) if u.root not in sys.stdlib_module_names] for i, a in answers.items()}
    by_env = collections.defaultdict(list)
    for i, us in uses.items():
        by_env[g.venv_name(by_id[i])].extend(paths_to_probe(us))
    probed = probe_envs(by_env)
    found = {}
    for i, us in uses.items():
        env = g.venv_name(by_id[i])
        if env in probed:
            found[i] = [x for x in diff(us, probed[env]) if x.kind != "DEPRECATED"]
    missing = [i for i in answers if g.venv_name(by_id[i]) not in probed and uses[i]]
    if missing:
        print(f"WARNING: probe produced no output for {len(missing)} problems (left unrepaired): {missing}")
    return found


def repair(args, ids: list[int]) -> Path:
    by_id = {int(r["example_id"]): r for r in g.load_dataset()}
    base_dir = g.run_dir(args, args.base)
    answers = {int(json.loads(l)["example_id"]): json.loads(l)["answer"]
               for l in (base_dir / "solutions.jsonl").read_text(encoding="utf8").splitlines()}
    ids = [i for i in ids if i in answers]
    label = {"A1": "A4", "A3": "A5"}.get(args.base, "PP_" + args.base)
    answers = {i: answers[i] for i in ids}
    stats = []
    for turn in range(1, args.turns + 1):
        issues = find_issues(answers, by_id)
        flagged = [i for i in ids if issues.get(i)]
        kinds = collections.Counter(x.kind for i in flagged for x in issues[i])
        stats.append((turn, len(flagged), dict(kinds)))
        print(f"[{label}] turn {turn}: {len(flagged)}/{len(ids)} problems have a verified error {dict(kinds)}")
        if not flagged:
            break
        arm = f"{label}" + ("" if turn == 1 else f"_t{turn}")
        reqs = []
        for i in flagged:
            row = by_id[i]
            user = PP_USER_TEMPLATE.format(
                problem=row["problem"], python_version=row["python_version"], library=row["library"],
                version=row["version"], additional_dependencies=row.get("additional_dependencies") or "",
                starting_code=row["starting_code"], solution=code_of(answers[i]), findings=render_findings(issues[i]))
            reqs.append((i, g.request_body(args.model, PP_SYSTEM_PROMPT, user, args.temperature, args.top_p, False,
                                           args.seed or None)))
        g.run_requests(args, arm, reqs, False)
        for i, body in reqs:
            a = g.cached_answer(args, arm, i, body)
            if a is not None:
                answers[i] = a
    else:
        issues = find_issues(answers, by_id)
        left = sum(1 for i in ids if issues.get(i))
        print(f"[{label}] after {args.turns} turns: {left}/{len(ids)} problems still have a verified error")
    (g.RUNS / f"{label}_{args.ids}_s{args.seed}_stats.json").write_text(json.dumps(stats))
    return g.score_solutions(args, g.write_solutions(g.run_dir(args, label), answers), ids)


def compare(args, label: str) -> None:
    """Paired comparison of the PinPoint arm against its base arm (hidden tests)."""
    def passed(arm):
        with (g.run_dir(args, arm) / "solutions_eval_results.csv").open(encoding="utf8") as f:
            import csv
            return {int(r["example_id"]): r["passed"] == "True" for r in csv.DictReader(f)}
    base, new = passed(args.base), passed(label)
    ids = sorted(set(base) & set(new))
    fixed = [i for i in ids if not base[i] and new[i]]
    broke = [i for i in ids if base[i] and not new[i]]
    print(f"paired vs {args.base} on {len(ids)} problems: fixed {len(fixed)}, broken {len(broke)} (net {len(fixed) - len(broke):+d})")
    print(f"  fixed: {fixed}\n  broken: {broke}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["repair"])
    ap.add_argument("--provider", choices=sorted(g.PROVIDERS), default="openai")
    ap.add_argument("--model", required=True)
    ap.add_argument("--ids", default="dev")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--top-p", dest="top_p", type=float, default=0.95)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--score-workers", type=int, default=2)
    ap.add_argument("--base", choices=["A1", "A3"], default="A1")
    ap.add_argument("--turns", type=int, default=3)
    args = ap.parse_args()
    rows = g.load_dataset()
    ids = g.select_ids(args.ids, rows)
    csv_path = repair(args, ids)
    g.report(csv_path, {int(r["example_id"]): r for r in rows})
    compare(args, {"A1": "A4", "A3": "A5"}[args.base])


if __name__ == "__main__":
    main()
