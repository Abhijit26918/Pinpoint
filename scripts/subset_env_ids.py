"""Print the example_ids that create_venvs.py needs to be given to build the
environments for the dev subset.

create_venvs.py builds one venv per distinct (python, library, version, deps) key and
keys it to the *first* dataset row with that key, so passing a subset id that is not that
first row would silently build nothing.
"""
import json
from pathlib import Path

DATASET = Path("external/GitChameleonBenchmark/dataset/dataset.jsonl")
SUBSET = Path("harness/dev_subset_ids.json")


def env_key(r: dict) -> tuple:
    return (r["python_version"], r["library"], r["version"], r.get("additional_dependencies", ""))


import sys

rows = [json.loads(line) for line in DATASET.read_text(encoding="utf8").splitlines() if line.strip()]
if len(sys.argv) > 1 and sys.argv[1] == "all":
    wanted = {int(r["example_id"]) for r in rows}
else:
    wanted = set(json.loads(SUBSET.read_text())["example_ids"])
first_id: dict[tuple, int] = {}
for r in rows:
    first_id.setdefault(env_key(r), int(r["example_id"]))
needed = sorted({first_id[env_key(r)] for r in rows if int(r["example_id"]) in wanted})
print(" ".join(map(str, needed)))
