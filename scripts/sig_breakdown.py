"""Roadmap step 2: A3 vs A5 on the problems where A3 had a verified finding, split by finding kind.
Hidden results are read only AFTER the findings are computed (analysis, not a loop)."""
import argparse, collections, csv, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness")); sys.path.insert(0, str(ROOT / "src"))
import gc_runner as g, gc_pinpoint as pp

ap = argparse.ArgumentParser(); ap.add_argument("--model", default="gpt-4.1-mini")
ap.add_argument("--ids", default="all"); ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--temperature", type=float, default=0.0); ap.add_argument("--top-p", dest="top_p", type=float, default=0.95)
ap.add_argument("--provider", default="openai"); ap.add_argument("--base", default="A3")
args = ap.parse_args()
rows = g.load_dataset(); by_id = {int(r["example_id"]): r for r in rows}
ans = {int(json.loads(l)["example_id"]): json.loads(l)["answer"]
       for l in (g.run_dir(args, "A3") / "solutions.jsonl").read_text(encoding="utf8").splitlines()}
issues = pp.find_issues(ans, by_id)
def passed(arm):
    with (g.run_dir(args, arm) / "solutions_eval_results.csv").open(encoding="utf8") as f:
        return {int(r["example_id"]): r["passed"] == "True" for r in csv.DictReader(f)}
a3, a5 = passed("A3"), passed("A5")
groups = collections.defaultdict(list)
for i, xs in issues.items():
    kinds = {x.kind for x in xs}
    if kinds: groups["any"].append(i)
    for k in kinds: groups[k].append(i)
    if kinds & {"SIGNATURE", "RENAMED", "MISSING", "MOVED"}: groups["sig-class (SIGNATURE+RENAMED+MISSING+MOVED)"].append(i)
print(f"{'kind':48s}  n  A3pass A5pass fixed broke")
for k, ids in sorted(groups.items()):
    print(f"{k:48s} {len(ids):2d}  {sum(a3[i] for i in ids):4d}   {sum(a5[i] for i in ids):4d}   "
          f"{sum(a5[i] and not a3[i] for i in ids):3d}   {sum(a3[i] and not a5[i] for i in ids):3d}")
