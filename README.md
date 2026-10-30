# PinPoint

> **Thesis:** Documentation is the wrong oracle for version-correct code. The installed
> object is the right one. Docs go stale; `inspect.signature()` cannot.

A runtime layer that checks LLM-generated code against the *actually installed* package —
by introspection, not documentation — and repairs it before delivery.

---

## Docs

| File | Read it when |
|---|---|
| `docs/05-project-story.md` | Start of every session. The whole story + current status |
| `docs/00-brief.md` | Now, and whenever scope is in question |
| `docs/01-related-work.md` | Week 1. What's taken, what's open, the positioning paragraph, scoop log |
| `docs/02-system-design.md` | Weeks 2–8, while building |
| `docs/03-eval-plan.md` | Weeks 3–10. Baselines, metrics, cost plan |
| `docs/04-timeline-and-slides.md` | Weekly. Milestones and the 5-slide map |

## The 30-second version

Every LLM writes code against the library version in its training data. You're on a newer
one. It writes `df.append()`, which pandas removed in 2.0, and the code breaks — or worse,
silently does the wrong thing.

Current fixes all feed the model **documentation**: retrieval, prompting, weight editing.
Published result: even with complete correct docs, only **66.36%** of generated code
actually executes.

PinPoint feeds it the **installed object instead** — real signatures, real type hints, real
captured deprecation warnings — and repairs against that.

## Setup

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # venv, benchmark clone, docker image
# fill in .env (see .env.example), then:
.venv\Scripts\python -m pytest -q
.venv\Scripts\python harness\gc_runner.py run --provider openai --model gpt-4.1-mini --ids dev
```

Python deps live in `.venv` (pinned in `requirements-dev.lock`). The benchmark's per-problem
library environments live in the Docker volume `gc_venvs`, not on the host.

## Use it

```powershell
pip install -e .            # stdlib-only, no dependencies; gives the `pinpoint` command
pinpoint check my_script.py                       # verify library calls against what is INSTALLED
pinpoint check my_script.py --python .venv\Scripts\python.exe --json
pinpoint repair my_script.py                      # ask a model to fix the findings; prints a diff
pinpoint repair my_script.py --write              # ...and apply it (needs OPENAI_API_KEY)
```

Demo on a library no model has seen (`examples/broken_halyard.py`):

```
$ pinpoint check examples/broken_halyard.py --path experiments/private_sdk
  line 12: RENAMED `halyard.Client.dequeue` - halyard.Client has no attribute 'dequeue'.  Did you mean: ...
  line 15: MISSING `halyard.Client.complete` - halyard.Client has no attribute 'complete'.
  line 20: SIGNATURE `halyard.Client.enqueue` - unexpected keyword argument 'ttl'. Installed: enqueue(self, queue, payload, *, delay=0.0, ...)
```

`check` exits 1 when it finds something, 0 when clean, 2 on a tool error. It only reports facts it verified in the
target interpreter (missing name, wrong keyword, wrong argument count); it does not judge logic. Uses inside a
`try/except` that catches the relevant error are treated as deliberate feature detection and skipped.

## Demo

```powershell
python demo/run_demo.py --step     # 5 acts, ~8 min, offline (recorded real runs); Enter advances
python demo/run_demo.py --act 3 --live   # the repair step calls the model for real (OPENAI_API_KEY)
```

Acts: (1) live check of a real installed library; (2) four real GitChameleon failures with the findings PinPoint derived
from the pinned package, the fix and the hidden-test result; (3) the invented `halyard` SDK: crash -> findings -> the exact
evidence the model sees -> repair -> the code runs; (4) a bug PinPoint cannot see; (5) the numbers.

## Results (details and caveats: `docs/03-eval-plan.md`)

GitChameleon 2.0, gpt-4.1-mini, 328 problems, 3 seeds, hidden tests, paired bootstrap 95% CI:
PinPoint over plain generation **+4.2 pts [+2.3, +6.2]**; over self-debug **+2.6 pts [+1.2, +4.4]**; it broke 0 problems.
Only ~16% of failures are visible to introspection; the rest are logic errors it cannot see.
On an invented private SDK (24 held-out tasks, code frozen first): no help 2/24, PinPoint 9/24, written docs 22/24 -
roughly half of what docs give when none exist. The ablation shows the key ingredient is listing what the installed
object really exposes. One model family; second model confirms the SDK result, inconclusive on GitChameleon.

## Status (2026-10-30)

- [x] Baselines reproduced (A1 47.9 vs published 44.2; A3 55.8 vs 68, gap explained in the eval plan)
- [x] Probe, diff, repair loop built and validated (0 false alarms on reference solutions)
- [x] GitChameleon A4/A5, 3 seeds; private-SDK case study with held-out tasks; ablation; second model
- [x] `pinpoint check` / `pinpoint repair` CLI
- [ ] Write-up and 5 slides

## Budget

$10 total, OpenAI only (OpenRouter had no credit). No GPU. Spend so far is well under budget; scoring time, not API cost, dominates.
