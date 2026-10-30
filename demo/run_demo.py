"""PinPoint demo. Five acts, about 8 minutes. Works offline by default (recorded real runs); --live calls the model.

    python demo/run_demo.py            # all acts, no pauses
    python demo/run_demo.py --step     # press Enter between acts (for presenting)
    python demo/run_demo.py --act 3    # one act only
    python demo/run_demo.py --live     # act 3 asks the model for real (needs OPENAI_API_KEY)

Act 1  The problem, on a real library you have installed (live introspection, no network)
Act 2  Four real benchmark failures: what the model wrote, what the INSTALLED package said, the fix, the test result
Act 3  A library no model has ever seen (invented 'halyard'): check -> evidence the model gets -> repair -> run it
Act 4  What PinPoint cannot see (honest limits)
Act 5  The numbers
"""
import argparse
import difflib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
from pinpoint.check import check_source, format_issue  # noqa: E402
from pinpoint.repair import (DEFAULT_TASK, SYSTEM_PROMPT, USER_TEMPLATE, code_of, openai_complete,  # noqa: E402
                             render_findings, repair_code)

os.system("")  # enables ANSI colours in the Windows console
B, DIM, RED, GRN, YEL, CYA, RST = "\033[1m", "\033[2m", "\033[31m", "\033[32m", "\033[33m", "\033[36m", "\033[0m"
SDK = str(ROOT / "experiments" / "private_sdk")
STEP = False


def title(n, text):
    print(f"\n{B}{CYA}{'=' * 78}\n ACT {n}: {text}\n{'=' * 78}{RST}")


def say(text):
    print(textwrap.fill(text, 100, replace_whitespace=False))


def pause():
    if STEP:
        input(f"{DIM}[Enter]{RST}")


def show_code(code, mark=()):
    for n, line in enumerate(code.rstrip("\n").splitlines(), 1):
        bad = n in mark
        print(f"  {RED if bad else DIM}{n:3d} | {line}{RST}" + (f"   {RED}<-- PinPoint{RST}" if bad else ""))


def show_diff(before, after):
    for line in difflib.unified_diff(before.splitlines(), after.splitlines(), "before", "after", lineterm="", n=1):
        if line.startswith(("---", "+++")):
            continue
        col = GRN if line.startswith("+") else RED if line.startswith("-") else DIM
        print(f"  {col}{line}{RST}")


def lines_of(findings):
    out = []
    for f in findings:
        try:
            out.append(int(f.split("line ", 1)[1].split(":", 1)[0]))
        except (IndexError, ValueError):
            pass
    return out


# ---------------------------------------------------------------------------------------------------------------
def act1():
    title(1, "LLMs write code for the library version they remember")
    say("An assistant writes code for packaging / pytest as they were in its training data. The installed versions are "
        "newer. Nothing 'reads the docs': PinPoint just asks the installed package whether each name exists.")
    code = (HERE / "drift_example.py").read_text(encoding="utf8")
    print(f"\n{B}Code the assistant wrote ({HERE.name}/drift_example.py):{RST}")
    show_code(code)
    import packaging
    import pytest
    print(f"\n{B}$ pinpoint check drift_example.py{RST}   {DIM}(this machine: packaging {packaging.__version__}, pytest {pytest.__version__}){RST}")
    issues, roots = check_source(code)
    for x in sorted(issues, key=lambda x: x.line):
        print(f"  {YEL}{format_issue(x)}{RST}")
    print(f"\n{DIM}Probed live, inside this interpreter. No documentation, no network. "
          f"(`packaging.version.LegacyVersion` was removed in packaging 22.){RST}")


def act2():
    title(2, "Real failures from a published benchmark (GitChameleon 2.0, gpt-4.1-mini)")
    cases = {c["id"]: c for c in json.loads((HERE / "gc_cases.json").read_text(encoding="utf8"))}
    say("Each case: a version-pinned task, the model's first answer (it FAILED the hidden tests), the finding PinPoint "
        "derived from the pinned package itself, the repaired code, and the hidden-test result. Recorded from the real runs.")
    for cid in (99, 51, 277, 252):
        c = cases[cid]
        print(f"\n{B}--- problem {cid}: {c['library']}=={c['version']} (python {c['python']}) ---{RST}")
        say("Task: " + c["problem"].strip().replace("\n", " ")[:260])
        print(f"\n{B}Model's first answer{RST} {RED}(hidden tests: FAIL){RST}")
        show_code(c["before"], mark=lines_of(c["findings"]))
        print(f"\n{B}PinPoint, asking the installed {c['library']} {c['version']}:{RST}")
        for f in c["findings"]:
            print(f"  {YEL}{f}{RST}")
        print(f"\n{B}Repair (model sees only those facts):{RST}")
        show_diff(c["before"], c["after"])
        print(f"\n  hidden tests: {RED}FAIL{RST} -> {GRN if c['hidden_after'] else RED}{'PASS' if c['hidden_after'] else 'FAIL'}{RST}")
        pause()


def run_snippet(code, test):
    p = subprocess.run([sys.executable, "-c", f"import halyard\n{code}\n{test}"], capture_output=True, text=True,
                       cwd=SDK, timeout=30)
    return p.returncode == 0, (p.stderr.strip().splitlines() or [p.stdout.strip()])[-1]


def act3(live):
    title(3, "A library no model has ever seen: halyard 2.3.0 (invented job-queue SDK)")
    say("Nothing about halyard exists in any training set or on the web, so there is nothing to retrieve. "
        "Only the installed package can tell us what is real.")
    src = (ROOT / "examples" / "broken_halyard.py").read_text(encoding="utf8")
    code = src[src.index("import halyard"):]
    print(f"\n{B}What the model wrote (guessing at a plausible API):{RST}")
    show_code(code)
    test = ("c = halyard.Client()\nfor i in range(3): c.enqueue('q', i)\nprint('processed', drain(c, 'q'))")
    ok, msg = run_snippet(code, test)
    print(f"\n{B}Run it:{RST} {GRN + 'ok' if ok else RED + 'CRASH'}  {msg}{RST}")

    print(f"\n{B}$ pinpoint check{RST}")
    issues, roots = check_source(code, extra_paths=[SDK])
    for x in sorted(issues, key=lambda x: x.line):
        print(f"  {YEL}{format_issue(x)}{RST}")
    print(f"\n{B}Exactly what the model is told{RST} {DIM}(facts from the installed package, not docs):{RST}")
    for ln in render_findings(issues).splitlines():
        print("  " + textwrap.shorten(ln, 330, placeholder=" ..."))
    pause()

    fixed_path = HERE / "cache" / "halyard_fixed.py"
    if live:
        print(f"\n{B}$ pinpoint repair{RST}  {DIM}(live model call){RST}")
        vers = f"halyard=={'2.3.0'}"
        new, left = repair_code(code, lambda c: check_source(c, extra_paths=[SDK])[0], openai_complete("gpt-4.1-mini"),
                                ".".join(map(str, sys.version_info[:3])), vers, turns=3, log=lambda s: print("  " + s))
    else:
        print(f"\n{B}$ pinpoint repair{RST}  {DIM}(recorded model output; --live to call the model){RST}")
        new, left = fixed_path.read_text(encoding="utf8"), check_source(fixed_path.read_text(encoding="utf8"), extra_paths=[SDK])[0]
    show_diff(code, new)
    print(f"\n{B}Re-check:{RST} {GRN if not left else RED}{len(left)} finding(s) left{RST}")
    ok, msg = run_snippet(new, test)
    print(f"{B}Run the repaired code:{RST} {GRN + 'ok' if ok else RED + 'CRASH'}  {msg}{RST}")
    print(f"\n{DIM}Note the model dropped `ttl=60` (in another run it turned it into `delay=60`). PinPoint guarantees the code "
          f"is *callable* on the installed version, not that it means what you intended. That is why repair prints a diff and --write is opt-in.{RST}")


def act4():
    title(4, "What PinPoint cannot see")
    code = (HERE / "limits_example.py").read_text(encoding="utf8")
    print(f"\n{B}Code with a real bug, using only names that exist:{RST}")
    show_code(code)
    issues, _ = check_source(code, extra_paths=[SDK])
    print(f"\n{B}$ pinpoint check{RST}  ->  {GRN}{len(issues)} findings{RST}")
    say("The loop acks jobs it never processed and returns the wrong count. Every call is valid for halyard 2.3.0, so "
        "introspection is silent. This is the ceiling: on GitChameleon only ~16% of failing answers contain a "
        "detectable name or signature error; the other ~84% are logic errors. PinPoint is a precise helper for "
        "version drift, not a correctness oracle, and it does not replace tests or documentation.")


def act5():
    title(5, "The numbers (all measured, with caveats in docs/03-eval-plan.md)")
    rows = [
        ("GitChameleon, 328 problems, 3 seeds, gpt-4.1-mini, hidden tests", ""),
        ("  plain generation   -> + PinPoint", "+4.2 pts   95% CI [+2.3, +6.2]   (0 problems broken)"),
        ("  self-debug         -> + PinPoint", "+2.6 pts   95% CI [+1.2, +4.4]   (0 problems broken)"),
        ("Invented SDK, 24 held-out tasks (code frozen before writing them)", ""),
        ("  no help / self-debug", "2/24  /  3/24"),
        ("  PinPoint on each", "9/24  /  11/24"),
        ("  written docs (upper bound, needs docs to exist)", "22/24"),
        ("Ablation: what evidence matters (invented SDK)", ""),
        ("  'this is wrong' / + suggestions / + signatures", "3-5/24"),
        ("  + what the installed object actually exposes", "7-10/24   <- the key ingredient"),
    ]
    for a, b in rows:
        print(f"  {B if not b else ''}{a:<66}{RST}{GRN}{b}{RST}")
    print(f"\n{DIM}One model family on the main benchmark; second model confirms the SDK result, inconclusive on GitChameleon. "
          f"A5 over self-debug (+2.6) is just under the 3-point bar we set in advance.{RST}")


def main():
    global STEP
    ap = argparse.ArgumentParser()
    ap.add_argument("--act", type=int, choices=range(1, 6))
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    STEP = a.step
    acts = {1: act1, 2: act2, 3: lambda: act3(a.live), 4: act4, 5: act5}
    for n in ([a.act] if a.act else sorted(acts)):
        acts[n]()
        pause()


if __name__ == "__main__":
    main()
