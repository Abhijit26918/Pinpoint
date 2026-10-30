"""The offline demo must keep running end to end (acts 1-5, no network, no Docker)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_offline_demo_runs():
    p = subprocess.run([sys.executable, str(ROOT / "demo" / "run_demo.py")], capture_output=True, text=True,
                       encoding="utf8", timeout=300)
    assert p.returncode == 0, p.stderr[-500:]
    assert "ACT 5" in p.stdout and "FAIL\x1b[0m -> \x1b[32mPASS" in p.stdout
    assert "0 finding(s) left" in p.stdout and "processed 3" in p.stdout
