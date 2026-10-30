import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
import gc_pinpoint as pp  # noqa: E402
from pinpoint.diff import Issue  # noqa: E402


def test_code_of_takes_first_fence_else_text():
    assert pp.code_of("hi\n```python\nx = 1\n```\nbye").strip() == "x = 1"
    assert pp.code_of("x = 2") == "x = 2"


def test_findings_quote_real_signature_and_suggestions():
    text = pp.render_findings([
        Issue("SIGNATURE", "lib.f", 3, "unexpected keyword argument 'a'", ["b"], signature="(x, *, b=1)"),
        Issue("RENAMED", "lib.old", 5, "lib has no attribute 'old'", ["lib.new"]),
        Issue("MISSING", "lib.gone", 7, "lib has no attribute 'gone'")])
    assert "f(x, *, b=1)" in text and "`lib.new`" in text and "no similarly named symbol" in text
    assert text.count("\n") == 2
