"""Roadmap step 3: paired bootstrap over problems, pooled over seeds (per-problem mean difference)."""
import csv, random
from pathlib import Path
RUNS = Path(__file__).resolve().parents[1] / "data/cache/runs"
def load(arm, s):
    with (RUNS / f"openai_gpt-4.1-mini_{arm}_s{s}_all/solutions_eval_results.csv").open(encoding="utf8") as f:
        return {int(r["example_id"]): r["passed"] == "True" for r in csv.DictReader(f)}
def boot(new, old, seeds, B=10000):
    d = {}
    for i in load(new, seeds[0]):
        d[i] = sum(load(new, s)[i] - load(old, s)[i] for s in seeds) / len(seeds)
    ids = sorted(d); rng = random.Random(0)
    m = sum(d.values()) / len(ids)
    bs = sorted(sum(d[rng.choice(ids)] for _ in ids) / len(ids) for _ in range(B))
    return 100 * m, 100 * bs[int(.025 * B)], 100 * bs[int(.975 * B)]
for s in (0, 1, 2):
    print(f"seed {s}: " + " | ".join(f"{a} {100*sum(load(a,s).values())/328:.1f}" for a in ("A1", "A3", "A4", "A5")))
print("pooled over 3 seeds (pts, 95% paired bootstrap CI):")
for new, old in (("A4", "A1"), ("A5", "A3"), ("A3", "A1"), ("A5", "A4")):
    m, lo, hi = boot(new, old, (0, 1, 2)); print(f"  {new}-{old}: {m:+.2f}  [{lo:+.2f}, {hi:+.2f}]")
