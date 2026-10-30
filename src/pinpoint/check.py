"""check: find the library calls in a piece of code and verify them against the INSTALLED packages.

    issues, roots = check_source(code, python="path/to/venv/python")   # default: the current interpreter

The probe (probe.py, stdlib only) runs inside the target interpreter, so the answers describe exactly the
environment the code will run in. DEPRECATED findings are informational (correct code often uses deprecated
APIs on purpose), so only MISSING / RENAMED / MOVED / SIGNATURE count as errors here.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from .diff import Issue, diff, paths_to_probe
from .resolve import resolve

PROBE = Path(__file__).with_name("probe.py")
ERROR_KINDS = ("MISSING", "RENAMED", "MOVED", "SIGNATURE")


class ProbeFailed(RuntimeError):
    pass


def _env(extra_paths) -> dict:
    env = dict(os.environ)
    if extra_paths:
        env["PYTHONPATH"] = os.pathsep.join([*map(str, extra_paths), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    return env


def run_probe(paths: list[str], python: str | None = None, extra_paths=(), cwd: str | None = None,
              timeout: int = 300) -> list[dict]:
    """Probe dotted paths inside `python` (default: this interpreter). Returns one result dict per path."""
    if not paths:
        return []
    p = subprocess.run([python or sys.executable, str(PROBE)], input=json.dumps({"paths": paths}), text=True,
                       capture_output=True, timeout=timeout, cwd=cwd, env=_env(extra_paths))
    if p.returncode != 0 or not p.stdout.strip():
        raise ProbeFailed(f"probe failed in {python or sys.executable}: {(p.stderr or p.stdout).strip()[-400:]}")
    return json.loads(p.stdout)["results"]


def installed_versions(roots: list[str], python: str | None = None, extra_paths=()) -> dict[str, str]:
    """Best effort: distribution version of each import root, as seen by the target interpreter."""
    code = ("import importlib.metadata as m, json, sys\n"
            "out = {}\n"
            "for r in json.loads(sys.argv[1]):\n"
            "    try:\n"
            "        out[r] = m.version(r)\n"
            "    except Exception:\n"
            "        pass\n"
            "print(json.dumps(out))")
    try:
        p = subprocess.run([python or sys.executable, "-c", code, json.dumps(roots)], text=True, capture_output=True,
                           timeout=60, env=_env(extra_paths))
        return json.loads(p.stdout) if p.returncode == 0 else {}
    except Exception:
        return {}


def check_source(code: str, python: str | None = None, extra_paths=(), cwd: str | None = None
                 ) -> tuple[list[Issue], list[str]]:
    """Return (issues, third-party import roots used). Standard-library imports are not checked."""
    uses = [u for u in resolve(code) if u.root not in sys.stdlib_module_names]
    roots = sorted({u.root for u in uses})
    if not uses:
        return [], roots
    paths = paths_to_probe(uses)
    results = dict(zip(paths, run_probe(paths, python, extra_paths, cwd)))
    return [x for x in diff(uses, results) if x.kind in ERROR_KINDS], roots


def format_issue(x: Issue) -> str:
    head = f"line {x.line}: {x.kind} `{x.path}`"
    if x.kind == "SIGNATURE":
        return f"{head} - {x.detail}. Installed: {x.path.rsplit('.', 1)[-1]}{x.signature}"
    hint = ""
    if x.suggestions:
        hint = ("  Defined in: " if x.kind == "MOVED" else "  Did you mean: ") + ", ".join(x.suggestions)
    return f"{head} - {x.detail}.{hint}"
