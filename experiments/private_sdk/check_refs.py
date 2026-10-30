"""Every task's reference solution must pass its visible and hidden tests; the bare stub must fail."""
import subprocess
import sys
from pathlib import Path

import importlib

_m = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "tasks")
PRE, T = _m.PRE, _m.T

HERE = Path(__file__).parent


def run(code: str) -> tuple[bool, str]:
    p = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True, text=True, timeout=60)
    return p.returncode == 0, p.stderr[-300:]


if __name__ == "__main__":
    bad = 0
    for t in T:
        ok_v, e1 = run(PRE + t["ref"] + "\n" + t["visible"])
        ok_h, e2 = run(PRE + t["ref"] + "\n" + t["hidden"])
        stub_v, _ = run(PRE + t["starter"] + "\n" + t["visible"])
        flag = "" if ok_v and ok_h and not stub_v else "  <-- PROBLEM"
        bad += bool(flag)
        print(f"{t['id']:2d} {t['stem']:22s} ref visible={ok_v} hidden={ok_h} stub-passes-visible={stub_v}{flag}")
        if not (ok_v and ok_h):
            print("   ", ((e1 or e2).strip().splitlines() or [""])[-1])
    print("tasks:", len(T), "problems:", bad)
