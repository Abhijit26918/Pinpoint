"""Command line: `pinpoint check FILE` and `pinpoint repair FILE`."""
import argparse
import difflib
import json
import sys
from pathlib import Path

from . import __version__
from .check import ProbeFailed, check_source, format_issue, installed_versions
from .repair import openai_complete, repair_code


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("file", help="Python file to check")
    p.add_argument("--python", help="interpreter whose installed packages are the ground truth (default: this one)")
    p.add_argument("--path", action="append", default=[], metavar="DIR",
                   help="extra directory on the target's import path (repeatable), e.g. a local library")


def cmd_check(a) -> int:
    code = Path(a.file).read_text(encoding="utf8")
    try:
        issues, roots = check_source(code, a.python, a.path)
    except (ProbeFailed, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps([{"kind": x.kind, "path": x.path, "line": x.line, "detail": x.detail,
                           "suggestions": x.suggestions, "signature": x.signature} for x in issues], indent=2))
    elif issues:
        print(f"{a.file}: {len(issues)} verified finding(s) against the installed packages ({', '.join(roots)})")
        for x in sorted(issues, key=lambda x: x.line):
            print("  " + format_issue(x))
    else:
        print(f"{a.file}: no verified findings ({', '.join(roots) or 'no third-party library calls found'})")
    return 1 if issues else 0


def cmd_repair(a) -> int:
    path = Path(a.file)
    code = path.read_text(encoding="utf8")

    def find(c):
        return check_source(c, a.python, a.path)[0]

    try:
        issues, roots = check_source(code, a.python, a.path)
        if not issues:
            print(f"{a.file}: nothing to repair (no verified findings).")
            return 0
        vers = installed_versions(roots, a.python, a.path)
        libs = ", ".join(f"{r}=={vers[r]}" if r in vers else r for r in roots)
        pyver = "the target interpreter's" if a.python else ".".join(map(str, sys.version_info[:3]))
        new, left = repair_code(code, find, openai_complete(a.model, a.base_url), pyver, libs, turns=a.turns,
                                log=lambda s: print(s, file=sys.stderr))
    except (ProbeFailed, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    diff = "".join(difflib.unified_diff(code.splitlines(True), new.splitlines(True),
                                        f"{a.file} (before)", f"{a.file} (after)"))
    print(diff or "(no change)")
    if left:
        print(f"{len(left)} finding(s) remain:", file=sys.stderr)
        for x in left:
            print("  " + format_issue(x), file=sys.stderr)
    if a.write and new != code:
        path.write_text(new, encoding="utf8")
        print(f"wrote {a.file}", file=sys.stderr)
    return 1 if left else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="pinpoint",
        description="Check and repair LLM-written code against the INSTALLED packages (introspection, not documentation).")
    ap.add_argument("--version", action="version", version=f"pinpoint {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="report calls that do not exist or do not fit in the installed packages")
    _common(c)
    c.add_argument("--json", action="store_true", help="machine-readable output")
    c.set_defaults(fn=cmd_check)
    r = sub.add_parser("repair", help="check, then ask a model to fix the findings (prints a diff; --write applies it)")
    _common(r)
    r.add_argument("--model", default="gpt-4.1-mini")
    r.add_argument("--base-url", help="OpenAI-compatible endpoint (default: api.openai.com, key from OPENAI_API_KEY)")
    r.add_argument("--turns", type=int, default=3)
    r.add_argument("--write", action="store_true", help="overwrite FILE with the repaired code")
    r.set_defaults(fn=cmd_repair)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
