"""Pick a deterministic 50-problem dev subset of GitChameleon 2.0.

Stratified by library (>=1 each, rest proportional) and biased toward the largest
environment groups so that few venvs have to be built.
"""
import collections
import json
import random
from pathlib import Path

SEED = 0
N = 50
DATASET = Path("external/GitChameleonBenchmark/dataset/dataset.jsonl")
OUT = Path("harness/dev_subset_ids.json")


def change_class(t: str) -> str:
    t = t.lower()
    if "argument" in t or "attribute" in t:
        return "argument/attribute"
    if "name" in t:
        return "name"
    if "deprecat" in t:
        return "deprecation"
    if "new" in t:
        return "new feature/func"
    return "other"


def env_key(r: dict) -> tuple:
    return (r["python_version"], r["library"], r["version"], r.get("additional_dependencies", ""))


def main() -> None:
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf8").splitlines() if line.strip()]
    rng = random.Random(SEED)
    by_lib = collections.defaultdict(list)
    for r in rows:
        by_lib[r["library"]].append(r)

    # quota: 1 per library, remainder by largest-remainder proportional share
    quota = {lib: 1 for lib in by_lib}
    spare = N - len(by_lib)
    shares = {lib: spare * len(v) / len(rows) for lib, v in by_lib.items()}
    for lib in quota:
        quota[lib] += int(shares[lib])
    leftover = N - sum(quota.values())
    for lib in sorted(shares, key=lambda k: shares[k] - int(shares[k]), reverse=True)[:leftover]:
        quota[lib] += 1

    chosen = []
    for lib, items in sorted(by_lib.items()):
        groups = collections.defaultdict(list)
        for r in items:
            groups[env_key(r)].append(r)
        # biggest env group first; within a group prefer unseen change classes
        picked, seen = [], set()
        for _, g in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            g = g[:]
            rng.shuffle(g)
            g.sort(key=lambda r: change_class(r["type_of_change"]) in seen)
            for r in g:
                if len(picked) >= quota[lib]:
                    break
                picked.append(r)
                seen.add(change_class(r["type_of_change"]))
            if len(picked) >= quota[lib]:
                break
        chosen.extend(picked)

    ids = sorted(int(r["example_id"]) for r in chosen)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"seed": SEED, "n": len(ids), "example_ids": ids}, indent=1))
    print(len(ids), "problems;", len({env_key(r) for r in chosen}), "of",
          len({env_key(r) for r in rows}), "environments")
    print(collections.Counter(change_class(r["type_of_change"]) for r in chosen))
    print(collections.Counter(r["python_version"] for r in chosen))
    print(sorted(collections.Counter(r["library"] for r in chosen).items(), key=lambda kv: -kv[1]))


if __name__ == "__main__":
    main()
