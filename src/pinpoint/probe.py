"""Introspection probe: report what the INSTALLED package actually exposes for dotted API paths.

Standalone and stdlib-only on purpose: it runs inside the pinned venv of the target library
(`python -I probe.py < request.json`), so it can never disagree with the installed version.

Request  (stdin JSON): {"paths": ["pandas.DataFrame.append", ...]}
Response (stdout JSON): {"python": "3.9.19", "results": [{...}, ...]}

Per path: status ok | missing | import_error, plus kind, signature/params, deprecation hints, the
module the object really lives in (moved symbols), and close-name candidates when it is missing
(renamed symbols). Nothing is executed beyond import and getattr.
"""
from __future__ import annotations  # the pinned venvs include Python 3.7: no `list[str]` at runtime

import difflib
import importlib
import inspect
import json
import sys
import warnings


def _import_prefix(parts: list[str]):
    """Import the longest importable module prefix of `parts`; return (module, remaining parts, error)."""
    err = None
    for n in range(len(parts), 0, -1):
        name = ".".join(parts[:n])
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                mod = importlib.import_module(name)
            return mod, parts[n:], None, [str(w.message) for w in caught
                                         if issubclass(w.category, (DeprecationWarning, FutureWarning))]
        except ImportError as e:
            err = err or f"{type(e).__name__}: {e}"
        except Exception as e:  # noqa: BLE001 - broken import of a real module still tells us something
            return None, parts, f"{type(e).__name__}: {e}", []
    return None, parts, err, []


def _kind(obj) -> str:
    if inspect.ismodule(obj):
        return "module"
    if inspect.isclass(obj):
        return "class"
    if inspect.isroutine(obj):
        return "function"
    if isinstance(obj, property):
        return "property"
    return "attribute"


def _params(sig: inspect.Signature) -> list[dict]:
    out = []
    for p in sig.parameters.values():
        out.append({
            "name": p.name,
            "kind": p.kind.name,
            "required": p.default is inspect.Parameter.empty and p.kind not in (
                inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD),
            "default": None if p.default is inspect.Parameter.empty else repr(p.default)[:80],
            "annotation": None if p.annotation is inspect.Parameter.empty else str(p.annotation)[:120],
        })
    return out


def _deprecated(obj) -> list[str]:
    hints = []
    if getattr(obj, "__deprecated__", None):  # PEP 702
        hints.append(str(obj.__deprecated__))
    doc = inspect.getdoc(obj) or ""
    for line in doc.splitlines():
        if ".. deprecated::" in line or line.strip().lower().startswith("deprecated"):
            hints.append(line.strip()[:160])
            break
    return hints


def _siblings(parent, missing: str, cap: int = 40) -> list[dict]:
    """What the parent object really exposes (public members, with signatures): the answer to "so what DOES exist?".
    Small namespaces are listed whole; large ones keep the names most similar to the missing one."""
    names = [n for n in dir(parent) if not n.startswith("_")]
    if len(names) > cap:
        names = sorted(names, key=lambda n: -difflib.SequenceMatcher(None, n, missing).ratio())[:cap]
    out = []
    for n in sorted(names):
        try:
            member = inspect.getattr_static(parent, n, None)
            member = getattr(parent, n) if member is None else member
            kind = _kind(member if not isinstance(member, (staticmethod, classmethod)) else member.__func__)
            sig = None
            try:
                sig = str(inspect.signature(getattr(parent, n)))
            except (TypeError, ValueError, AttributeError):
                pass
        except Exception:  # noqa: BLE001 - a property that raises must not hide the other members
            kind, sig = "attribute", None
        out.append({"name": n, "kind": kind, "signature": sig})
    return out


def _moved(root: str, name: str) -> list[str]:
    """Already-imported submodules of `root` that define `name` (a symbol that moved). No side effects:
    only module __dict__s are inspected, so lazy modules are not triggered."""
    found = []
    for modname, mod in list(sys.modules.items()):
        if mod is None or not (modname == root or modname.startswith(root + ".")):
            continue
        if any(seg.startswith("_") for seg in modname.split(".")[1:]):
            continue  # private modules are implementation detail, not a place to move to
        try:
            if name in vars(mod):
                found.append(f"{modname}.{name}")
        except TypeError:
            pass
    return sorted(found)[:5]


def _probe_path(path: str) -> dict:
    parts = path.split(".")
    res = {"path": path, "status": "import_error", "kind": None, "signature": None, "params": None,
           "deprecated": [], "resolved_module": None, "candidates": [], "moved_to": [], "descriptor": None,
           "siblings": [], "error": None}
    mod, rest, err, warns = _import_prefix(parts)
    if mod is None:
        res["error"] = err
        return res
    obj, parent = mod, mod
    for i, attr in enumerate(rest):
        parent = obj
        try:
            obj = getattr(parent, attr)
        except AttributeError:
            res.update(status="missing", error=f"{'.'.join(parts[:len(parts) - len(rest) + i])} has no attribute {attr!r}")
            res["candidates"] = difflib.get_close_matches(attr, [a for a in dir(parent) if not a.startswith("__")],
                                                          n=5, cutoff=0.6)
            res["siblings"] = _siblings(parent, attr)
            if inspect.ismodule(parent):  # a method/attribute of an instance or class cannot "move" between modules
                res["moved_to"] = _moved(parts[0], attr)
            return res
        except Exception as e:  # noqa: BLE001 - lazy-loading modules can raise anything
            res.update(status="import_error", error=f"{type(e).__name__}: {e}")
            return res
    res["status"], res["kind"] = "ok", _kind(obj)
    if rest and inspect.isclass(parent):  # tells the diff whether `self` is part of the signature
        res["descriptor"] = type(inspect.getattr_static(parent, rest[-1], None)).__name__
    try:
        sig = inspect.signature(obj)
        res["signature"], res["params"] = str(sig), _params(sig)
    except (TypeError, ValueError):
        pass  # builtins/C extensions without text signatures: kind is still reported
    res["deprecated"] = _deprecated(obj)  # import-time warnings are about the package, not this object
    real = getattr(obj, "__module__", None) or (getattr(parent, "__name__", None) if res["kind"] == "attribute" else None)
    res["resolved_module"] = real
    return res


def probe_path(path: str) -> dict:
    """Never raises: a package that blows up on import/inspection (e.g. Django without settings) is one
    `probe_error`, not a dead probe process that loses every other path in the environment."""
    try:
        return _probe_path(path)
    except BaseException as e:  # noqa: BLE001
        return {"path": path, "status": "probe_error", "kind": None, "signature": None, "params": None,
                "deprecated": [], "resolved_module": None, "candidates": [], "moved_to": [], "descriptor": None, "siblings": [],
                "error": f"{type(e).__name__}: {e}"[:300]}


def probe(paths: list[str]) -> dict:
    return {"python": ".".join(map(str, sys.version_info[:3])), "results": [probe_path(p) for p in paths]}


if __name__ == "__main__":
    print(json.dumps(probe(json.load(sys.stdin)["paths"])))
