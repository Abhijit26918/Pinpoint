"""How good is the diff? Run resolve+probe+diff on code with known outcomes.

  gt : benchmark reference solutions (correct) -> every issue is a false alarm
  A1 / A3 : model answers with hidden-test outcomes -> issues should concentrate in failing answers

Probing happens in each problem's pinned venv (one docker container). Needs Docker Desktop running.
Only non-stdlib roots are analysed (stdlib is not what version-conditioned problems are about).

Usage: python scripts/eval_diff.py [--arms gt,A1,A3]
"""
import argparse
import collections
import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "src"))
import gc_runner as g  # noqa: E402
from pinpoint.diff import diff, paths_to_probe  # noqa: E402
from pinpoint.resolve import resolve  # noqa: E402

WORK = ROOT / "data/cache/diff_eval"
RUNS = {"gt": "ground_truth", "A1": "openai_gpt-4.1-mini_A1_s0_all", "A3": "openai_gpt-4.1-mini_A3_s0_all",
        "A2k3": "openai_gpt-4.1-mini_A2k3_s0_all"}


def load_arm(arm: str):
    d = g.RUNS / RUNS[arm]
    codes = {int(json.loads(l)["example_id"]): json.loads(l)["answer"]
             for l in (d / "solutions.jsonl").read_text(encoding="utf8").splitlines()}
    outcome = {}
    f = d / "solutions_eval_results.csv"
    if f.exists():
        with f.open(encoding="utf8") as fh:
            outcome = {int(r["example_id"]): r["passed"] == "True" for r in csv.DictReader(fh)}
    return codes, outcome


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="gt,A1,A3")
    args = ap.parse_args()
    arms = args.arms.split(",")
    rows = {int(r["example_id"]): r for r in g.load_dataset()}
    data = {a: load_arm(a) for a in arms}
    stdlib = sys.stdlib_module_names

    uses = {(a, i): [u for u in resolve(code) if u.root not in stdlib]
            for a, (codes, _) in data.items() for i, code in codes.items()}
    by_env = collections.defaultdict(set)
    for (a, i), us in uses.items():
        by_env[g.venv_name(rows[i])].update(paths_to_probe(us))

    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    shutil.copy(ROOT / "src/pinpoint/probe.py", WORK / "probe.py")
    envs = sorted(by_env)
    for e in envs:
        (WORK / f"req_{e}.json").write_text(json.dumps({"paths": sorted(by_env[e])}))
    script = "; ".join(
        f"timeout 600 /app/.dataset_venvs/{e}/bin/python -I /work/probe.py < /work/req_{e}.json > /work/out_{e}.json 2> /work/err_{e}.txt"
        for e in envs)
    p = g.docker_run([f"{WORK}:/work"], script, 4 * 3600)
    print("docker exit", p.returncode)

    probed = {}
    for e in envs:
        out = WORK / f"out_{e}.json"
        if out.exists() and out.stat().st_size:
            paths = json.loads((WORK / f"req_{e}.json").read_text())["paths"]
            probed[e] = dict(zip(paths, json.loads(out.read_text())["results"]))
    print(f"probed {len(probed)}/{len(envs)} environments")

    summary = {}
    for a in arms:
        codes, outcome = data[a]
        per_id = {}
        for i in codes:
            env = g.venv_name(rows[i])
            if env in probed:
                per_id[i] = diff(uses[(a, i)], probed[env])
        kinds = collections.Counter(x.kind for iss in per_id.values() for x in iss)
        flagged = {i for i, iss in per_id.items() if iss}
        line = f"{a}: {len(flagged)}/{len(per_id)} problems flagged; issues by kind {dict(kinds)}"
        print(line)
        if outcome:
            for label, want in (("pass hidden", True), ("fail hidden", False)):
                ids = [i for i in per_id if outcome.get(i) is want]
                n = sum(i in flagged for i in ids)
                print(f"   {label}: flagged {n}/{len(ids)} = {100 * n / max(1, len(ids)):.0f}%")
        summary[a] = {i: [vars(x) for x in iss] for i, iss in per_id.items() if iss}
    (WORK / "issues.json").write_text(json.dumps(summary, indent=1, default=str))
    for a in arms:
        print(f"\n--- sample issues, {a}")
        for i, iss in list(summary[a].items())[:12]:
            x = iss[0]
            print(f"  #{i} {x['kind']:10s} {x['path']}: {x['detail'][:90]} {x['suggestions'][:2]}")


if __name__ == "__main__":
    main()
