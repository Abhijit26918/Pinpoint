"""Roadmap step 6: which part of the introspection evidence does the work? Re-render the SAME findings at four
levels of detail and repair with each (held-out tasks, gpt-4.1-mini, base = P1 and P3). Detection is unchanged;
only what the model is told differs. Uses the frozen PinPoint code; no tuning.
  L0 names only        : "line N: `path` is wrong for the installed version"
  L1 + error detail    : adds what is wrong (missing / bad argument) and 'did you mean' suggestions
  L2 + signature       : adds the installed signature for call mismatches
  L3 full PinPoint     : the frozen renderer unchanged (adds the members the installed parent exposes + fuller wording)
Usage: python experiments/private_sdk/ablate.py --tasks=tasks_heldout --model gpt-4.1-mini"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run  # noqa: E402  (parses --tasks= from argv)

pp, g = run.pp, run.g


_FULL = pp.render_findings


def render(level):
    if level == 3:
        return _FULL  # exactly the frozen PinPoint rendering
    def f(issues):
        out = []
        for n, x in enumerate(issues, 1):
            if level == 0:
                out.append(f"{n}. line {x.line}: `{x.path}` is wrong for the installed version.")
                continue
            sug = ", ".join(f"`{s}`" for s in x.suggestions) if x.suggestions else ""
            if x.kind == "SIGNATURE":
                s = f" The installed signature is `{x.path.rsplit('.', 1)[-1]}{x.signature}`." if level >= 2 else ""
                out.append(f"{n}. line {x.line}: call to `{x.path}`: {x.detail}.{s}")
            else:
                s = f" Names that do exist nearby: {sug}." if sug else ""
                m = pp._members(x) if level >= 3 else ""
                out.append(f"{n}. line {x.line}: `{x.path}` does not exist in the installed version ({x.detail}).{s}{m}")
        return "\n".join(out)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-4.1-mini")
    ap.add_argument("--tasks", default="tasks")
    a = ap.parse_args()
    args = argparse.Namespace(provider="openai", model=a.model, seed=0, workers=4, top_p=0.95)
    p1 = run.generate(args, "PS_P1" + run.TAG, run.user_prompt)
    p3 = run.self_debug(args, p1, "PS_P3" + run.TAG)
    print(f"\n{'level':28s} base=P1  base=P3   (hidden /{len(run.T)})")
    print(f"{'no PinPoint':28s} {sum(h for _, h in run.score(p1).values()):4d}     {sum(h for _, h in run.score(p3).values()):4d}")
    for lvl, name in enumerate(["L0 names only", "L1 + detail/suggestions", "L2 + signatures", "L3 + member listing"]):
        pp.render_findings = render(lvl)
        row = []
        for base, bn in ((p1, "P1"), (p3, "P3")):
            ans = run.pinpoint(args, base, f"ABL{lvl}_{bn}" + run.TAG)
            row.append(sum(h for _, h in run.score(ans).values()))
        print(f"{name:28s} {row[0]:4d}     {row[1]:4d}")


if __name__ == "__main__":
    main()
