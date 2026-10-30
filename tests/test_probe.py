import json
import subprocess
import sys
from pathlib import Path

from pinpoint.probe import probe, probe_path

PROBE_FILE = Path(__file__).resolve().parents[1] / "src/pinpoint/probe.py"


def test_function_signature_and_params():
    r = probe_path("json.dumps")
    assert r["status"] == "ok" and r["kind"] == "function"
    names = {p["name"] for p in r["params"]}
    assert {"obj", "indent", "sort_keys"} <= names
    assert next(p for p in r["params"] if p["name"] == "obj")["required"]
    assert not next(p for p in r["params"] if p["name"] == "indent")["required"]


def test_missing_attribute_offers_rename_candidates():
    r = probe_path("json.dumpz")
    assert r["status"] == "missing" and "dumps" in r["candidates"]


def test_missing_module_is_import_error():
    r = probe_path("no_such_pkg_xyz.thing")
    assert r["status"] == "import_error" and r["error"]


def test_module_class_and_moved_symbol():
    assert probe_path("os.path")["kind"] == "module"
    assert probe_path("inspect.Parameter")["kind"] == "class"
    assert probe_path("os.path.join")["resolved_module"] in ("posixpath", "ntpath")  # re-exported symbol


def test_nested_method_resolution():
    r = probe_path("json.JSONEncoder.default")
    assert r["status"] == "ok" and r["kind"] == "function"


def test_runs_standalone_in_isolated_mode():
    """The probe is piped into a venv's python with -I, so it must work as a plain script."""
    out = subprocess.run([sys.executable, "-I", str(PROBE_FILE)], input=json.dumps({"paths": ["json.dumps", "json.nope"]}),
                         capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    assert [r["status"] for r in data["results"]] == ["ok", "missing"]


def test_probe_batch_shape():
    out = probe(["json.loads"])
    assert out["python"].count(".") == 2 and out["results"][0]["path"] == "json.loads"


def test_attribute_of_instance_is_not_reported_as_moved():
    # json.decoder has JSONDecoder; a missing attribute on a class must never produce moved_to
    r = probe_path("json.JSONDecoder.nope")
    assert r["status"] == "missing" and r["moved_to"] == []


def test_probe_path_never_raises(monkeypatch):
    import pinpoint.probe as pr
    monkeypatch.setattr(pr, "_probe_path", lambda p: (_ for _ in ()).throw(RuntimeError("boom")))
    r = pr.probe_path("x.y")
    assert r["status"] == "probe_error" and "boom" in r["error"]
