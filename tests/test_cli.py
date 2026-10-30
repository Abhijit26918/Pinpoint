"""CLI / tool tests: no network, a fake library on disk, a fake model."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
from pinpoint import repair as R  # noqa: E402
from pinpoint.check import check_source  # noqa: E402
from pinpoint.cli import main  # noqa: E402

LIB = '''
class Box:
    def put(self, item, *, count=1):
        return item

    def take(self):
        return 1


def helper(a, b=2):
    return a
'''


@pytest.fixture
def libdir(tmp_path):
    d = tmp_path / "libs"
    d.mkdir()
    (d / "fakebox.py").write_text(LIB)
    return str(d)


def write(tmp_path, code):
    f = tmp_path / "t.py"
    f.write_text(code)
    return str(f)


BAD = "import fakebox\n\ndef f(b: fakebox.Box):\n    b.putt(1)\n    return fakebox.helper(1, 2, 3)\n"
GOOD = "import fakebox\n\ndef f(b: fakebox.Box):\n    b.put(1, count=2)\n    return fakebox.helper(1)\n"


def test_check_flags_missing_and_signature(libdir):
    issues, roots = check_source(BAD, extra_paths=[libdir])
    assert roots == ["fakebox"]
    assert {(x.kind, x.path) for x in issues} == {("RENAMED", "fakebox.Box.putt"), ("SIGNATURE", "fakebox.helper")}


def test_check_clean_code_has_no_findings(libdir):
    assert check_source(GOOD, extra_paths=[libdir])[0] == []


def test_stdlib_only_code_is_not_probed():
    assert check_source("import json\njson.nope()\n") == ([], [])


def test_cli_exit_codes(tmp_path, libdir):
    assert main(["check", write(tmp_path, GOOD), "--path", libdir]) == 0
    assert main(["check", write(tmp_path, BAD), "--path", libdir]) == 1


def test_cli_json_payload(tmp_path, libdir, capsys):
    main(["check", write(tmp_path, BAD), "--path", libdir, "--json"])
    out = json.loads(capsys.readouterr().out)
    assert {o["kind"] for o in out} == {"RENAMED", "SIGNATURE"}


def test_missing_interpreter_raises(tmp_path):
    with pytest.raises(OSError):
        check_source(BAD, python=str(tmp_path / "no-python"))


def test_repair_loop_with_fake_model(tmp_path, libdir):
    seen = []

    def fake(system, user):
        seen.append(user)
        return "```python\n" + GOOD + "```"
    find = lambda c: check_source(c, extra_paths=[libdir])[0]  # noqa: E731
    new, left = R.repair_code(BAD, find, fake, "3.x", "fakebox", turns=3)
    assert left == [] and new == GOOD and len(seen) == 1
    assert "fakebox.Box.putt" in seen[0] and "provides:" in seen[0]  # member listing reaches the prompt


def test_repair_stops_when_model_changes_nothing(libdir):
    find = lambda c: check_source(c, extra_paths=[libdir])[0]  # noqa: E731
    new, left = R.repair_code(BAD, find, lambda s, u: "```python\n" + BAD + "```", "3.x", "fakebox", turns=3)
    assert new == BAD and left


def test_cli_repair_writes_only_with_flag(tmp_path, libdir, monkeypatch):
    f = write(tmp_path, BAD)
    monkeypatch.setattr("pinpoint.cli.openai_complete", lambda *a, **k: (lambda s, u: "```python\n" + GOOD + "```"))
    assert main(["repair", f, "--path", libdir]) == 0
    assert Path(f).read_text() == BAD
    assert main(["repair", f, "--path", libdir, "--write"]) == 0
    assert Path(f).read_text() == GOOD


def test_prompts_match_the_experiment_harness():
    """The shipped tool must use the same wording that was evaluated."""
    import gc_pinpoint as pp
    assert R.SYSTEM_PROMPT == pp.PP_SYSTEM_PROMPT
    from pinpoint.diff import Issue
    xs = [Issue("RENAMED", "m.f", 3, "no attribute", ["m.g"]), Issue("SIGNATURE", "m.h", 4, "bad kw", [], signature="(a)"),
          Issue("MISSING", "m.z", 5, "gone", [], siblings=[{"name": "q", "kind": "function", "signature": "(x)"}])]
    assert R.render_findings(xs) == pp.render_findings(xs)
