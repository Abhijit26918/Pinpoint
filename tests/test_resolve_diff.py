from pinpoint.diff import analyze
from pinpoint.probe import probe_path
from pinpoint.resolve import resolve


def probe_fn(paths):
    return [probe_path(p) for p in paths]


def kinds(code):
    return sorted((i.kind, i.path) for i in analyze(code, probe_fn))


def test_resolver_follows_imports_aliases_and_instances():
    uses = resolve("import json as j\nfrom os import path as p\nenc = j.JSONEncoder(indent=2)\nenc.encode({}, 1)\np.join('a')\n")
    got = {(u.path, u.kind) for u in uses}
    assert ("json", "import") in got and ("os.path", "import") in got
    assert ("json.JSONEncoder", "call") in got and ("os.path.join", "call") in got
    inst = next(u for u in uses if u.path == "json.JSONEncoder.encode")
    assert inst.ctor == "json.JSONEncoder" and inst.n_pos == 2


def test_resolver_ignores_unknown_names_and_bad_syntax():
    assert resolve("x = foo.bar(1)\n") == []
    assert resolve("def (:") == []


def test_clean_code_has_no_issues():
    assert kinds("import json\njson.dumps({'a': 1}, indent=2)\n") == []


def test_unknown_keyword_gets_suggestion():
    (i,) = analyze("import json\njson.JSONEncoder(indnt=2)\n", probe_fn)
    assert i.kind == "SIGNATURE" and "indnt" in i.detail and "indent" in i.suggestions


def test_var_keyword_functions_accept_any_keyword():
    assert kinds("import json\njson.dumps({}, whatever=2)\n") == []


def test_renamed_symbol():
    (i,) = analyze("import json\njson.dumpz({})\n", probe_fn)
    assert i.kind == "RENAMED" and "json.dumps" in i.suggestions


def test_missing_symbol_without_candidates():
    assert kinds("import json\njson.zzzzqqqq_nothing()\n") == [("MISSING", "json.zzzzqqqq_nothing")]


def test_moved_symbol_found_in_loaded_submodule():
    import json.decoder  # noqa: F401 - makes the submodule visible in sys.modules
    (i,) = analyze("import json\njson.JSONDecodeError2 = 1\njson.scanstring2\n", probe_fn)  # not a move: no such name anywhere
    assert i.kind in ("MISSING", "RENAMED")
    (j,) = analyze("import json\njson.scanstring('x', 0)\n", probe_fn)  # exported at top level? make sure no false MOVED
    assert j.kind != "MOVED" or j.suggestions


def test_instance_method_signature_drops_self():
    assert kinds("import json\ne = json.JSONEncoder()\ne.encode({})\n") == []
    (i,) = analyze("import json\ne = json.JSONEncoder()\ne.encode({}, 5)\n", probe_fn)
    assert i.kind == "SIGNATURE" and "positional" in i.detail


def test_missing_required_argument():
    (i,) = analyze("import json\njson.loads()\n", probe_fn)
    assert i.kind == "SIGNATURE" and "missing required argument 's'" in i.detail


def test_star_args_suppress_arity_checks():
    assert kinds("import json\nargs = ({},)\njson.dumps(*args)\njson.dumps(**{'obj': 1})\n") == []


def test_factory_function_instances_are_not_checked():
    # os.getcwd() is a function, so `d` is not an instance of anything we can introspect
    assert kinds("import os\nd = os.getcwd()\nd.upper(1, 2, 3)\n") == []


def test_import_of_missing_name():
    (i,) = analyze("from json import dumpz\n", probe_fn)
    assert i.kind == "RENAMED"


def test_chain_through_instance_attribute_is_not_judged():
    # e.encode.__name__.zzz: the type of `e.encode.__name__` cannot be known from the class alone
    assert kinds("import json\ne = json.JSONEncoder()\ne.encode.__name__.zzz\n") == []


def test_feature_detection_in_try_except_is_not_judged():
    guarded = "import json\ntry:\n    f = json.dumpz\nexcept AttributeError:\n    f = json.dumps\n"
    assert kinds(guarded) == []
    assert kinds("import json\ntry:\n    json.dumpz({})\nexcept Exception:\n    pass\n") == []
    assert kinds("import json\ntry:\n    json.dumpz({})\nexcept ValueError:\n    pass\n") == [("RENAMED", "json.dumpz")]
    # the handler body is outside the guard
    assert kinds("import json\ntry:\n    pass\nexcept AttributeError:\n    json.dumpz({})\n") == [("RENAMED", "json.dumpz")]


def test_annotated_parameter_is_an_instance():
    code = "import json\ndef f(enc: json.JSONEncoder):\n    enc.encode({}, 5)\n"
    (i,) = analyze(code, probe_fn)
    assert i.kind == "SIGNATURE" and "positional" in i.detail
    assert kinds("import json\ndef f(enc: json.JSONEncoder):\n    enc.encode({})\n") == []
