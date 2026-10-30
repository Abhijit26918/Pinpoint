"""Score the benchmark's own reference solutions in our built environments.

Any problem that fails here has a broken environment (or broken test), so no model can pass it.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
import gc_runner as g  # noqa: E402

args = argparse.Namespace(score_workers=6)
rows = g.load_dataset()
ids = sorted(int(r["example_id"]) for r in rows)
csv_path = g.score_solutions(args, g.RUNS / "ground_truth" / "solutions.jsonl", ids)
res = g.read_results(csv_path)
bad = [r for r in res if r["passed"] != "True"]
print(f"reference solutions passing hidden tests: {len(res) - len(bad)}/{len(res)}")
print("failing example_ids:", sorted(int(r["example_id"]) for r in bad))
