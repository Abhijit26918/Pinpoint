import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
import gc_runner as g  # noqa: E402

ROW = {"library": "torch", "version": "1.9.0", "python_version": "3.7", "problem": "P",
       "starting_code": "import torch\n", "additional_dependencies": "scipy==1.7.3 numpy==1.21.6"}


def test_prompt_pins_version_by_default():
    assert "torch==1.9.0" in g.render_user(ROW)
    assert "<library>\ntorch\n</library>" in g.render_user(ROW, "name")


def test_cache_key_stable_and_sensitive():
    body = g.request_body("m", "s", "u", 0.0, 0.95, True, None)
    k = g.cache_key("openai", "A1", 0, 0, body)
    assert k == g.cache_key("openai", "A1", 0, 0, dict(body))
    assert k != g.cache_key("openai", "A1", 1, 0, body)
    assert k != g.cache_key("openai", "A1", 0, 0, g.request_body("m", "s", "u2", 0.0, 0.95, True, None))
    assert "seed" not in body and g.request_body("m", "s", "u", 0.0, 0.95, True, 3)["seed"] == 3


def test_extract_answer():
    assert g.extract_answer('{"Answer": "x", "Explanation": "y"}', True) == "x"
    assert g.extract_answer("not json", True) == "not json"
    assert g.extract_answer('{"Answer": "x"}', False) == '{"Answer": "x"}'


def test_venv_name_matches_upstream_hash():
    # upstream: sha256("-".join([py, lib, ver, deps]))[:12]; problem 0 built earlier as 927f7310e738
    assert g.venv_name(ROW) == "gcham_venv_927f7310e738"


def test_dev_subset_ids_valid():
    ids = g.select_ids("dev", g.load_dataset())
    assert len(ids) == 50 and len(set(ids)) == 50
