# PinPoint — System Design

---

## 1. Pipeline

```
          user request + target environment
                      │
                      ▼
            ┌──────────────────┐
            │   LLM generates  │   (cached — see §6)
            └────────┬─────────┘
                     ▼
 ┌─────────────── PinPoint ────────────────────────────┐
 │                                                     │
 │  [1] RESOLVE                                        │
 │      AST-parse the code → every imported symbol     │
 │      and attribute access. Map to the module        │
 │      actually importable in the pinned venv.        │
 │                                                     │
 │  [2] INTROSPECT  ◄── the contribution               │
 │      inspect.signature()      → real parameters     │
 │      typing.get_type_hints()  → real types          │
 │      inspect.getmembers()     → moved/renamed       │
 │      warnings.catch_warnings  → DeprecationWarning  │
 │      __module__, __qualname__ → relocations         │
 │                                                     │
 │  [3] DIFF                                           │
 │      what the code assumes  vs  what exists         │
 │      → MISSING | RENAMED | MOVED | SIGNATURE |      │
 │        DEPRECATED | TYPE | OK                       │
 │                                                     │
 │  [4] REPAIR                                         │
 │      prompt carries the REAL signature, not docs.   │
 │      one finding per repair turn. budget: 3.        │
 │                                                     │
 │  [5] VERIFY                                         │
 │      re-run [1]–[3]; then execute in the sandbox    │
 └─────────────────────────────────────────────────────┘
                     ▼
            code that runs on THIS install
```

**Input** → request + pinned environment. **Process** → resolve, introspect, diff, repair,
verify. **Output** → executable code plus a report of what was corrected and why.

## 2. The introspection probe

Runs **inside** the pinned venv as a subprocess; results come back as JSON. Never import
user packages into the main process.

```python
# probe.py — executed with the pinned interpreter
def probe(dotted_name: str) -> dict:
    obj, missing = resolve(dotted_name)          # importlib walk
    if missing:
        return {"status": "MISSING",
                "near": close_matches(dotted_name),   # getmembers + difflib
                "moved_to": search_namespace(dotted_name.split(".")[-1])}
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        sig  = str(inspect.signature(obj))
        hints = typing.get_type_hints(obj)
    return {"status": "OK", "signature": sig, "hints": hints,
            "doc": inspect.getdoc(obj),
            "deprecated": [str(x.message) for x in w],
            "module": getattr(obj, "__module__", None)}
```

**Edge cases to handle explicitly** (these will be a slide's worth of engineering):
C-extension functions with no retrievable signature, decorated functions (`__wrapped__`),
overloads, `*args`/`**kwargs` passthroughs, properties and descriptors, lazy submodule
imports, and import side effects. Where introspection fails, fall back to docstring
parsing and record it — the fallback rate is a number worth reporting.

## 3. Repair prompt shape

The whole point is what goes in the context:

```
Your code calls:        pd.DataFrame.append(other, ignore_index=True)
Installed:              pandas 2.2.3
Introspection:          'append' not found on DataFrame
Nearest in namespace:   concat (module-level), _append (private)
Deprecation record:     removed in 2.0; use pandas.concat
Real signature:         concat(objs, *, axis=0, join='outer',
                               ignore_index=False, ...)

Rewrite using only what exists above.
```

No documentation. No retrieval. Only facts read off the installed objects.

## 4. Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11 |
| Static pass | `ast` (stdlib) |
| Introspection | `inspect`, `typing`, `importlib`, `warnings` |
| Isolation | one Docker image per (library, version); `uv` for fast venv builds |
| LLM access | Ollama local (dev) · OpenRouter (eval) · Kaggle + vLLM (batch) |
| Eval set | GitChameleon 2.0 |
| Orchestration | plain Python + SQLite cache. No framework. |

## 5. Arms to compare

| Arm | Grounding |
|---|---|
| A1 Greedy | nothing |
| A2 Docs-RAG | retrieved documentation (published baseline) |
| A3 Self-debug | execution error traces (published baseline) |
| **A4 PinPoint** | **introspection** |
| A5 PinPoint + self-debug | both |

A5 matters: the two sources are complementary — introspection catches it *before*
execution, errors catch what introspection can't see.

## 6. Caching (decide this on day one)

SQLite, keyed by `(model, model_version, problem_id, config, seed)`. Cache the generation,
the probe result, and the execution trace separately. Generations are the expensive part
and should be produced **once per model** and reused by every downstream experiment.

Without this you will spend 10× the budget and burn free-tier quota on work you already
did.

## 7. Runner requirements

Free tiers rate-limit and change without notice. Build in from the start:
retry with exponential backoff · resumable state (restart mid-run, skip completed) ·
provider swap by config · per-problem timeout · full JSONL logging of every attempt.

Losing a half-finished run at 2am is the most predictable failure in this project.
