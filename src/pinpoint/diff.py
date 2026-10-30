"""Diff: compare how generated code uses a library with what the probe says is installed.

    issues = diff(uses, probe_results)

Issue kinds: MISSING, RENAMED (close name exists in the same parent), MOVED (name now lives in another
module), SIGNATURE (unknown keyword / too many positionals / missing required argument), DEPRECATED.
Every issue carries the evidence from the probe, which is what the repair prompt is built from.
"""
import difflib
from dataclasses import dataclass, field

from .resolve import Use

POSITIONAL = ("POSITIONAL_ONLY", "POSITIONAL_OR_KEYWORD")
KEYWORDABLE = ("POSITIONAL_OR_KEYWORD", "KEYWORD_ONLY")


@dataclass
class Issue:
    kind: str
    path: str
    line: int
    detail: str
    suggestions: list[str] = field(default_factory=list)
    signature: str | None = None
    siblings: list[dict] = field(default_factory=list)  # what the parent object really exposes


ANY = {"*", "Exception", "BaseException"}


def _guarded(u: Use, *names: str) -> bool:
    """True if an enclosing try/except catches one of `names` (or anything): deliberate feature detection."""
    return bool(u.caught & (ANY | set(names)))


def paths_to_probe(uses: list[Use]) -> list[str]:
    """Everything the diff will want to look up (use paths plus the constructors behind instance uses)."""
    out: dict[str, None] = {}
    for u in uses:
        if u.ctor:
            out[u.ctor] = None
        out[u.path] = None
    return list(out)


def _effective_params(params: list[dict], drop_self: bool) -> list[dict]:
    if drop_self and params and params[0]["kind"] in POSITIONAL:
        return params[1:]
    return params


def check_call(u: Use, params: list[dict], drop_self: bool) -> list[tuple[str, list[str]]]:
    """Return [(message, suggestions)] for a call that does not fit the signature."""
    ps = _effective_params(params, drop_self)
    positional = [p for p in ps if p["kind"] in POSITIONAL]
    has_var_kw = any(p["kind"] == "VAR_KEYWORD" for p in ps)
    has_var_pos = any(p["kind"] == "VAR_POSITIONAL" for p in ps)
    accepted = [p["name"] for p in ps if p["kind"] in KEYWORDABLE]
    problems: list[tuple[str, list[str]]] = []

    if not has_var_kw:
        for k in u.kwargs:
            if k not in accepted:
                problems.append((f"unexpected keyword argument '{k}'",
                                 difflib.get_close_matches(k, accepted, n=3, cutoff=0.5)))
    if not u.star_args and not has_var_pos and u.n_pos > len(positional):
        problems.append((f"{u.n_pos} positional arguments given but at most {len(positional)} accepted", []))
    if not u.star_args and not u.star_kwargs:
        for i, p in enumerate(positional):
            if p["required"] and i >= u.n_pos and not (p["kind"] == "POSITIONAL_OR_KEYWORD" and p["name"] in u.kwargs):
                problems.append((f"missing required argument '{p['name']}'", []))
        for p in ps:
            if p["kind"] == "KEYWORD_ONLY" and p["required"] and p["name"] not in u.kwargs:
                problems.append((f"missing required keyword-only argument '{p['name']}'", []))
    return problems


def diff(uses: list[Use], results: dict[str, dict]) -> list[Issue]:
    """`results` maps dotted path -> probe result. Uses whose path was not probed are ignored."""
    issues: list[Issue] = []
    seen: set[tuple] = set()

    def add(issue: Issue):
        key = (issue.kind, issue.path, issue.detail)
        if key not in seen:
            seen.add(key)
            issues.append(issue)

    for u in uses:
        if u.ctor:  # instance use: only valid if the constructor really is a class
            c = results.get(u.ctor)
            if not c or c["status"] != "ok" or c["kind"] != "class":
                continue
        if u.ctor and "." in u.path[len(u.ctor) + 1:]:
            continue  # chain through an instance attribute (app.config.x): its type is unknowable from the class
        r = results.get(u.path)
        if r is None:
            continue
        if r["status"] == "missing":
            if _guarded(u, "AttributeError", "ImportError", "ModuleNotFoundError"):
                continue
            parent, _, name = u.path.rpartition(".")
            if r["moved_to"]:
                add(Issue("MOVED", u.path, u.line, f"'{name}' no longer exists in {parent}; it is now defined in another module",
                          r["moved_to"]))
            elif r["candidates"]:
                add(Issue("RENAMED", u.path, u.line, r["error"] or "missing", [f"{parent}.{c}" for c in r["candidates"]],
                          siblings=r.get("siblings", [])))
            else:
                add(Issue("MISSING", u.path, u.line, r["error"] or "missing", siblings=r.get("siblings", [])))
            continue
        if r["status"] != "ok":
            continue
        if r["deprecated"]:
            add(Issue("DEPRECATED", u.path, u.line, "; ".join(r["deprecated"])[:200], signature=r["signature"]))
        if u.kind == "call" and r["params"] is not None and r["kind"] in ("function", "class"):
            drop_self = bool(u.ctor) and r.get("descriptor") == "function"
            if _guarded(u, "TypeError"):
                continue
            for msg, sugg in check_call(u, r["params"], drop_self):
                add(Issue("SIGNATURE", u.path, u.line, msg, sugg, signature=r["signature"]))
    return issues


def analyze(code: str, probe_fn) -> list[Issue]:
    """code -> issues. `probe_fn(paths: list[str]) -> list[dict]` runs the probe (in-process or in a venv)."""
    from .resolve import resolve
    uses = resolve(code)
    if not uses:
        return []
    paths = paths_to_probe(uses)
    return diff(uses, dict(zip(paths, probe_fn(paths))))

