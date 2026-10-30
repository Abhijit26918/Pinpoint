"""Private-library case study: an invented SDK (halyard) that no model has seen and no public docs describe.

Arms (all gpt-4.1-mini, greedy):
  P1  no help                         P2  hand-written API reference in the prompt (docs exist = upper bound)
  P3  self-debug (visible-test trace) P4  PinPoint on P1 (introspect installed halyard, diff, repair <=3 turns)
  P5  PinPoint on P3
Hidden tests are never used inside any loop. Scoring is local (subprocess), no Docker.

Usage: python experiments/private_sdk/run.py --model gpt-4.1-mini
"""
import argparse
import collections
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
import gc_pinpoint as pp  # noqa: E402
import gc_runner as g  # noqa: E402
from pinpoint.diff import diff, paths_to_probe  # noqa: E402
from pinpoint.resolve import resolve  # noqa: E402
import importlib  # noqa: E402

_TASKS = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--tasks=')), 'tasks')
PRE, T = importlib.import_module(_TASKS).PRE, importlib.import_module(_TASKS).T
TAG = '' if _TASKS == 'tasks' else '_' + _TASKS  # separates arm names and result files

WORK = ROOT / "data/cache/psdk"
LIB, VERSION, PYV = "halyard", "2.3.0", ".".join(map(str, sys.version_info[:3]))
DOCS = (HERE / "docs.md").read_text(encoding="utf8")


def run_code(code: str, timeout: int = 30) -> tuple[bool, str]:
    try:
        p = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:  # e.g. generated code that sleeps on a logical-clock SDK
        return False, f"TimeoutError: the code did not finish within {timeout} seconds"
    return p.returncode == 0, (p.stderr or p.stdout)[-1500:]


def user_prompt(t: dict, docs: bool = False) -> str:
    text = g.USER_TEMPLATE.format(library=f"{LIB}=={VERSION}", python_version=PYV, problem=t["desc"], starting_code=t["starter"])
    return text + ("\n\n5. API reference for the required library:\n<api_reference>\n" + DOCS + "\n</api_reference>" if docs else "")


def generate(args, arm: str, builder) -> dict[int, str]:
    reqs = [(t["id"], g.request_body(args.model, g.SYSTEM_PROMPT, builder(t), 0.0, args.top_p, False, None)) for t in T]
    g.run_requests(args, arm, reqs, False)
    return {i: g.cached_answer(args, arm, i, b) or "" for i, b in reqs}


def self_debug(args, base: dict[int, str], label: str) -> dict[int, str]:
    out, reqs = dict(base), []
    for t in T:
        ok, trace = run_code(PRE + pp.code_of(base[t["id"]]) + "\n" + t["visible"])
        if ok:
            continue
        user = g.SD_USER_TEMPLATE.format(problem=t["desc"], python_version=PYV, library=LIB, version=VERSION,
                                         additional_dependencies="", starting_code=t["starter"],
                                         solution=pp.code_of(base[t["id"]]), trace=trace)
        reqs.append((t["id"], g.request_body(args.model, g.SD_SYSTEM_PROMPT, user, 0.0, args.top_p, False, None)))
    g.run_requests(args, label, reqs, False)
    for i, b in reqs:
        out[i] = g.cached_answer(args, label, i, b) or base[i]
    print(f"[{label}] {len(reqs)}/{len(T)} answers failed the visible test and were retried")
    return out


def probe_local(paths: list[str]) -> dict[str, dict]:
    WORK.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "src/pinpoint/probe.py", WORK / "probe.py")
    env = {**os.environ, "PYTHONPATH": str(HERE)}
    p = subprocess.run([sys.executable, str(WORK / "probe.py")], input=json.dumps({"paths": paths}), cwd=HERE, env=env,
                       capture_output=True, text=True, timeout=120, check=True)
    return dict(zip(paths, json.loads(p.stdout)["results"]))


def find_issues(answers: dict[int, str]):
    uses = {i: [u for u in resolve(pp.code_of(a)) if u.root == LIB] for i, a in answers.items()}
    paths = sorted({p for us in uses.values() for p in paths_to_probe(us)})
    probed = probe_local(paths) if paths else {}
    return {i: [x for x in diff(us, probed) if x.kind != "DEPRECATED"] for i, us in uses.items()}


def pinpoint(args, base: dict[int, str], label: str, turns: int = 3) -> dict[int, str]:
    answers = dict(base)
    by_id = {t["id"]: t for t in T}
    for turn in range(1, turns + 1):
        issues = find_issues(answers)
        flagged = [i for i in answers if issues[i]]
        print(f"[{label}] turn {turn}: {len(flagged)}/{len(T)} have a verified error {dict(collections.Counter(x.kind for i in flagged for x in issues[i]))}")
        if not flagged:
            break
        arm, reqs = label + ("" if turn == 1 else f"_t{turn}"), []
        for i in flagged:
            t = by_id[i]
            user = pp.PP_USER_TEMPLATE.format(problem=t["desc"], python_version=PYV, library=LIB, version=VERSION,
                                              additional_dependencies="", starting_code=t["starter"],
                                              solution=pp.code_of(answers[i]), findings=pp.render_findings(issues[i]))
            reqs.append((i, g.request_body(args.model, pp.PP_SYSTEM_PROMPT, user, 0.0, args.top_p, False, None)))
        g.run_requests(args, arm, reqs, False)
        for i, b in reqs:
            a = g.cached_answer(args, arm, i, b)
            if a:
                answers[i] = a
    return answers


def score(answers: dict[int, str]) -> dict[int, tuple[bool, bool]]:
    return {t["id"]: (run_code(PRE + pp.code_of(answers[t["id"]]) + "\n" + t["visible"])[0],
                      run_code(PRE + pp.code_of(answers[t["id"]]) + "\n" + t["hidden"])[0]) for t in T}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-4.1-mini")
    ap.add_argument("--tasks", default="tasks")
    a = ap.parse_args()
    args = argparse.Namespace(provider="openai", model=a.model, seed=0, workers=4, top_p=0.95)

    arms = {}
    arms["P1 no help"] = generate(args, "PS_P1" + TAG, user_prompt)
    arms["P2 written docs"] = generate(args, "PS_P2" + TAG, lambda t: user_prompt(t, docs=True))
    arms["P3 self-debug"] = self_debug(args, arms["P1 no help"], "PS_P3" + TAG)
    arms["P4 PinPoint (on P1)"] = pinpoint(args, arms["P1 no help"], "PS_P4" + TAG)
    arms["P5 PinPoint (on P3)"] = pinpoint(args, arms["P3 self-debug"], "PS_P5" + TAG)

    results = {k: score(v) for k, v in arms.items()}
    print(f"\n{'arm':22s} hidden  visible")
    for k, r in results.items():
        print(f"{k:22s} {sum(h for _, h in r.values()):2d}/{len(T)}   {sum(v for v, _ in r.values()):2d}/{len(T)}")
    for new, old in (("P4 PinPoint (on P1)", "P1 no help"), ("P5 PinPoint (on P3)", "P3 self-debug")):
        fixed = [i for i in range(len(T)) if results[new][i][1] and not results[old][i][1]]
        broke = [i for i in range(len(T)) if results[old][i][1] and not results[new][i][1]]
        print(f"{new} vs {old}: fixed {len(fixed)} {fixed}, broken {len(broke)} {broke}")
    (ROOT / f"data/cache/psdk_results{TAG}_{a.model}.json").write_text(json.dumps(
        {k: {str(i): list(v) for i, v in r.items()} for k, r in results.items()}, indent=1))
    (ROOT / f"data/cache/psdk_answers{TAG}_{a.model}.json").write_text(json.dumps({k: {str(i): v for i, v in a.items()} for k, a in arms.items()}, indent=1))


if __name__ == "__main__":
    main()
