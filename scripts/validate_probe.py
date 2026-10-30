"""Validate the introspection probe in the real pinned environments.

For every problem, probe the dotted `api_calls` listed for its (working) reference solution inside that
problem's pinned venv. Roots that are not importable (local variables like `input_tensor.numpy`) are
counted separately: they need the AST resolver, not the probe. Everything else should be `ok`; a
`missing` here would mean the probe, not the library, is wrong.
One docker container, one probe process per environment. Needs Docker Desktop running.

Usage: python scripts/validate_probe.py [--limit N]
"""
import argparse
import collections
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
import gc_runner as g  # noqa: E402

WORK = ROOT / "data/cache/probe_validation"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only the first N environments (debug)")
    args = ap.parse_args()

    rows = g.load_dataset()
    by_env = collections.defaultdict(list)
    for r in rows:
        by_env[g.venv_name(r)].append(r)
    envs = sorted(by_env)[:args.limit or None]

    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    shutil.copy(ROOT / "src/pinpoint/probe.py", WORK / "probe.py")
    for env in envs:
        paths = sorted({c for r in by_env[env] for c in r["api_calls"] if "." in c})
        (WORK / f"req_{env}.json").write_text(json.dumps({"paths": paths}))
    script = "; ".join(
        f"timeout 300 /app/.dataset_venvs/{e}/bin/python -I /work/probe.py < /work/req_{e}.json > /work/out_{e}.json 2> /work/err_{e}.txt"
        for e in envs)
    p = g.docker_run([f"{WORK}:/work"], script, 3 * 3600)
    print("docker exit", p.returncode, p.stderr[-300:])

    tally = collections.Counter()
    bad = []
    for env in envs:
        out = WORK / f"out_{env}.json"
        n_req = len(json.loads((WORK / f"req_{env}.json").read_text())["paths"])
        if not out.exists() or out.stat().st_size == 0:
            tally["env_failed"] += 1
            bad.append((env, "no output", (WORK / f"err_{env}.txt").read_text()[-200:] if (WORK / f"err_{env}.txt").exists() else ""))
            tally["paths_in_failed_env"] += n_req
            continue
        for res in json.loads(out.read_text())["results"]:
            if res["status"] == "ok":
                tally["ok"] += 1
            elif res["status"] == "import_error":
                tally["root_not_importable"] += 1
            else:
                tally["MISSING"] += 1
                bad.append((env, res["path"], res["error"], res["candidates"]))
    print(dict(tally))
    for b in bad[:40]:
        print(" ", b)
    (WORK / "summary.json").write_text(json.dumps({"tally": tally, "bad": bad}, default=str, indent=1))


if __name__ == "__main__":
    main()
