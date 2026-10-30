"""Collect real GitChameleon cases (A1 failed, PinPoint A4 fixed) with the findings PinPoint produced, for the offline demo.
Findings are computed on the A1 answers; hidden-test outcomes come from the stored scoring runs (analysis only)."""
import csv, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness")); sys.path.insert(0, str(ROOT / "src"))
import gc_runner as g, gc_pinpoint as pp
from pinpoint.check import format_issue
import argparse
args = argparse.Namespace(provider="openai", model="gpt-4.1-mini", seed=0, ids="all")
rows = {int(r["example_id"]): r for r in g.load_dataset()}
def answers(arm):
    return {int(json.loads(l)["example_id"]): json.loads(l)["answer"]
            for l in (g.run_dir(args, arm) / "solutions.jsonl").read_text(encoding="utf8").splitlines()}
def passed(arm):
    with (g.run_dir(args, arm) / "solutions_eval_results.csv").open(encoding="utf8") as f:
        return {int(r["example_id"]): r["passed"] == "True" for r in csv.DictReader(f)}
a1, a4, p1, p4 = answers("A1"), answers("A4"), passed("A1"), passed("A4")
fixed = [i for i in a1 if not p1[i] and p4.get(i)]
issues = pp.find_issues({i: a1[i] for i in fixed}, rows)
cases = []
for i in fixed:
    r = rows[i]
    cases.append(dict(id=i, library=r["library"], version=r["version"], python=r["python_version"], problem=r["problem"],
                      starting_code=r["starting_code"], before=pp.code_of(a1[i]), after=pp.code_of(a4[i]),
                      findings=[format_issue(x) for x in issues.get(i, [])], model_findings=pp.render_findings(issues.get(i, [])),
                      kinds=sorted({x.kind for x in issues.get(i, [])}),
                      hidden_before=p1[i], hidden_after=p4[i]))
out = ROOT / "demo/gc_cases.json"; out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(cases, indent=1), encoding="utf8")
for c in cases:
    print(c["id"], c["library"], c["version"], c["kinds"], len(c["before"]), "|", (c["findings"] or ["-"])[0][:110])
