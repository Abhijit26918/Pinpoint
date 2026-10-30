# PinPoint — Evaluation Plan

---

## 1. Benchmark

**GitChameleon 2.0** — 328 manually authored, version-conditioned Python problems with
assertion-based unit tests and a clean Docker container per problem. Reports both a
*visible* test (shown to the model during self-debug) and a *hidden* test.

Do not build your own benchmark. Four exist and yours would be trusted less.

## 2. Published baselines to beat

| Condition | Hidden-test success |
|---|---|
| Greedy, large enterprise models | ~48–51% (o1 highest at 51.2) |
| Llama 3.1 greedy → self-debug | 30% → 52.1% |
| GPT-4.1-mini greedy → self-debug | 44% → 68% |
| Best self-debug | 70.4% (Gemini 2.0 Flash) |
| GPT-4.1 + RAG k=3 | 48.5% → 58.5% |
| Multi-step sandbox agent | ~55% |

**Pick a model from this list that is available on a free tier.** Llama-family models are
widely available free and already have a published number. Using an unbenchmarked model
costs you both money and your comparison.

### 2a. Paper read-through: GitChameleon 2.0 (arXiv 2507.12367v2) — 2026-10-28

Source for everything below: arXiv HTML v2, first ~100k of 173k chars (appendices, incl.
prompt templates in App. I, **not yet read**). Table 1 column headers were ambiguous in
extraction, so **re-check any number against the PDF before it goes on a slide.**

**Protocol.** 328 problems, 26 libraries (versions 2014–2023, >1k-star repos). Hidden tests
= ranking metric; one visible test = self-debug feedback. Greedy: temp 0, top_p 0.95,
structured output (`Answer` + `Explanation`). Target version is stated in the prompt.
Sampling (temp 0.8, 10 seeds) is within ±2 pts of greedy for most models. No pass@k.
Secondary metric: API Hit Rate.

**Baselines (greedy hidden / visible %), models plausible for us:**

| Model | Hidden | Visible | Notes |
|---|---|---|---|
| Llama 3.1 Instruct Turbo | 30.2 | 38.1 | self-debug → 52.1 hidden |
| Llama 3.3 70B Instruct Turbo | 36.3 | 43.3 | |
| Llama 4 Maverick | 40.8 | 46.6 | RAG k=3: 45.1 |
| GPT-4.1-mini | 44.2 | 50.0 | self-debug → 68 hidden |
| GPT-4.1-nano | 33.8 | 35.1 | |
| GPT-4o-mini | 37.2 | 46.3 | |
| GPT-4.1 | 48.5 | 49.1 | RAG k=3: 58.5 |

Others: Claude 3.7 Sonnet 48.8, Gemini 2.0 Flash 44.2 (self-debug 70.4 per our earlier note),
Gemini 2.5 Pro 50.0, o1 51.2 (top). RAG: DocPrompting over 536 docs,
text-embedding-3-large, k=1/3, gains up to ~10 pts, smaller models gain less.
Self-debug: +10–20 hidden; visible/hidden gap widens for every model (their Fig. 6).

**Environment.** Docker container per problem. Repo: `mrcabbage972/GitChameleonBenchmark`
(Apache-2.0); dataset on HF `cabbage972/GitChameleon-2.0` (config `problems`). Needs
Python 3.9+, Poetry, **Docker**. Run: `make evals-setup`, then
`evaluate --solution-path X --workers N`.

**Appendix read (from the local PDF, `papers/01-gitchameleon-2.0.pdf`, figs 17-23)**
- Table 1 re-checked against the PDF text: the numbers in the shortlist above are correct
  (row labels were shifted in the first extraction only). Added: self-debug **visible**
  numbers, Llama 3.1 69.2, Llama 3.3 70B 70.1, Maverick 72.3, GPT-4.1-mini 79.3 (hidden
  52.1 / 53.0 / 58.5 / 68.0). So the Llama 3.1 gap goes 7.9 → 17.1 pts with self-debug.
- Every cell carries ±~2.5-2.8 (binomial SE on 328 problems). **"Within a few points" for
  the gate should mean within ~1 SE (about 2.5-3 pts); 95% CI is about ±5.**
- **A1 prompt (Fig 17):** system prompt "You are a skilled Python programmer…", 6 rules
  (use the library, incorporate starter code, markdown code block, clean/commented, output
  only the code block), then user prompt with tags `<library>`, `<python>`,
  `<coding_problem>`, `<starter_code>`. Structured output `Answer`+`Explanation`; temp 0,
  top_p 0.95. Note the shown user prompt has *library* and *Python version* tags; whether
  the library version is inside `library` is not clear. Check against the dataset fields and
  repo code before running.
- **A3 self-debug (Fig 18):** single round, only on problems that failed greedy. Inputs:
  problem, python version, library, version, extra dependencies, starter code, previous
  solution, top-level trace of the **visible** test (plus the model's own explanation).
  Output: one corrected code block. Not iterative, so our "3-turn budget" for PinPoint is
  not a like-for-like match; run A3 as published *and* optionally a 3-turn variant.
- **A2 RAG (Fig 20):** system prompt + `{context}` of top-k docs + the same user prompt as
  the query. Corpus is the per-problem relevant API docs (536 docs), embedded with
  text-embedding-3-large. We would need to rebuild that corpus (check whether the dataset
  ships the doc links).
- Libraries (26): PyTorch, Geopandas, NLTK, NetworkX, GeoPy, Gradio, scikit-learn,
  Matplotlib, PyCaret, pandas, NumPy, LightGBM, spaCy, Django, Flask, Jinja, SymPy, seaborn,
  mitmproxy, pytest, Falcon, Tornado, Plotly, Librosa, Pillow, tqdm, Kymatio (list as
  printed; some overlap in count). Note several are heavy installs.

**Harness inspection (repo at `external/GitChameleonBenchmark`, commit 3a1b604, read not yet run)**
- Docker Desktop 29.1.3 + WSL2 (Ubuntu 22.04) work on this machine; image
  `mrcabbage972/gitchameleon:latest` pulled (3.05 GB). Poetry is not installed on the host
  and does not need to be; everything runs in the image.
- It is **one image + per-environment venvs**, not one container per problem. The image
  holds pyenv Pythons 3.7.17/3.9.19/3.10.14; `create_venvs.py` pip-installs each problem's
  pinned library + deps into `.dataset_venvs/gcham_venv_<hash>`. Only **99 distinct
  environments** serve all 328 problems (Python 3.10: 219 problems, 3.7: 67, 3.9: 42).
  Biggest groups: librosa 42, scipy 40, sympy 33, flask 22, falcon 21, torch 18.
- Upstream bind-mounts `./.dataset_venvs` from the host. On Windows that is slow and the
  venvs use `--copies` plus Linux paths, so use a **Docker named volume** (`gc_venvs`).
  `evaluate`/`make run-eval` also pass `-it`, which fails without a TTY; our runner should
  call `docker run` itself without it.
- **Solution file:** JSONL, one `{"example_id": "...", "answer": "<text with a ```python
  block>"}` per line (`answer`/`solution`/`output` accepted). Code is extracted by regex on
  the first ```python fence; if there is no fence the whole text is used.
- **Scoring:** hidden = pytest on `hidden_tests/test_sample_<id>.py` importing `sample_<id>`;
  visible = solution + the dataset's `test` field run as a script. 240 s timeout each.
  Output CSV has `passed`, `compiled`, `passed_manual` (visible), `output`, `output_manual`.
  The CSV's failure text is what the A3 self-debug arm and error-class labelling consume.
- **Correction:** the dataset already labels each problem with `type_of_change`
  (free text, 21 variants). Rough grouping: argument/attribute 108, new func/feature 99,
  name 57, deprecation 13, other 51. So section 4's error classes can start from these
  labels instead of only tracebacks. Caveat: they label the *benchmark change*, not what
  the model got wrong, and the grouping above is mine and rough.
- Dataset fields: `python_version, library, version, problem, starting_code, example_id,
  test (visible), solution, type_of_change, name_of_class_or_func, additional_dependencies,
  functional, webdev, solution_api_call, api_calls, release_date, docs`. `docs` holds
  per-problem doc URLs, which is the A2 RAG corpus source.
- **Smoke test passed (2026-10-28):** built problem 0's env (torch 1.9.0, py3.7, scipy) in
  named volume `gc_venvs`; the ground-truth solution scores hidden 6/6 and visible pass;
  a deliberately wrong answer scores 0/1 on both, so the scorer discriminates.
  Commands used (Windows Git Bash needs `MSYS_NO_PATHCONV=1`):
  `docker run --rm -e PIP_DEFAULT_TIMEOUT=300 -e PIP_RETRIES=10 -v gc_venvs:/app/.dataset_venvs IMAGE -c "pyenv global 3.9 && poetry run python gitchameleon/create_venvs.py --start N --end N --base_path .dataset_venvs --dataset dataset.jsonl --concurrency 1"`
  then `run_eval.py --dataset_file dataset.jsonl --solution_file /work/sol.jsonl --env_dir .dataset_venvs --test_dir hidden_tests --workers 1`
  with a host folder mounted at `/work` (the CSV is written next to the solution file).
- **Costs measured:** one env with torch took 6.7 min (first try failed on a PyPI read
  timeout; the script deletes failed envs, so always set the pip timeout/retry env vars).
  Eval of one problem ~9 s. Docker disk now: images 9.2 GB, volume 2 GB (one env), build
  cache 5.3 GB. Budget roughly 99 envs; torch-heavy ones are the big ones, so build only the
  envs a 50-problem dev subset needs, then the rest before the full run. Check D: free space
  (120 GB at start).
- **Dev subset:** `scripts/make_dev_subset.py` (seed 0) wrote `harness/dev_subset_ids.json`:
  50 problems, all 26 libraries, **26 of 99 environments**. Change classes: argument/attribute
  19, new feature 13, name 10, other 7, deprecation 1 (too few deprecations to analyse on dev;
  fine for the full run). Python 3.10: 35, 3.7: 10, 3.9: 5.
- **OpenRouter models (public API, 2026-10-28):** no `:free` Llama in the catalogue, so the
  "free tier" plan in section 2 does not hold, but cost is tiny. Per million tokens
  (in/out): llama-3.1-8b-instruct $0.05/$0.08; llama-3.1-70b-instruct $0.40/$0.40;
  llama-3.3-70b-instruct $0.10/$0.32; llama-4-maverick $0.19/$0.65; gpt-4.1-mini $0.40/$1.60.
  A full 328-problem greedy run is roughly 0.2M in + 0.1M out tokens, i.e. about $0.02 (8B)
  to $0.25 (gpt-4.1-mini). The $10 budget is ample. To settle the "Turbo" size, run both
  llama-3.1-8b and -70b on the 50 subset and see which lands near 30% (SE is ~6.5 pts at n=50).
- **Runner built (2026-10-28):** `harness/gc_runner.py` (stdlib only): `generate` (SQLite cache
  at `data/cache/generations.sqlite`, keyed on the full request, resumable, parallel),
  `score` (exports solutions, refuses to score if any needed venv is missing, runs the
  upstream scorer in Docker, prints hidden/visible with 95% CI and a by-class split), `run`.
  `tests/test_gc_runner.py`: 5 offline tests pass (use `.venv`, gitignored). Live check on
  problems 0-1 with gpt-4.1-mini: 0/2 pass, failures are genuine (hallucinated
  `torch.log0p`; numpy domain error), so the pipeline is sound. Cost of that check: ~1.4k tokens.
- **A1 on the 50-problem dev subset (2026-10-29), gpt-4.1-mini, greedy (temp 0, top_p 0.95),
  structured output, prompt `library==version`:** hidden **23/50 = 46.0%** (95% CI +/-13.8),
  visible 32/50 = 64.0%. Published full-set value is 44.2% hidden / 50.0% visible; the
  hidden figure is consistent but n=50 cannot confirm it. By class (hidden): argument/attribute
  10/19, name 3/10, new feature 6/13, other 3/7, deprecation 1/1 (too small to read much into).
  Cost: 17.6k tokens in, 12.5k out. First 26 envs built with 0 failures, 9.9 GB.
  The full-set reproduction (all 328) is the real gate; building the remaining 73 envs now.
- **A1 FULL SET (328), gpt-4.1-mini, greedy (2026-10-29): hidden 157/328 = 47.9%
  (95% CI 42.5-53.3), visible 179/328 = 54.6%.** Published: 44.2% hidden / 50.0% visible.
  Gap +3.7 hidden, +4.6 visible: inside the CI and about 1 SE of the paper's own +/-2.7, but
  above the ~3 pt line set earlier, and both metrics lean the same way. Plausible causes:
  newer gpt-4.1-mini snapshot, prompt rendering (`library==version` assumed), structured
  output. Scorer validity was checked (ground truth passes, wrong answer fails), so it is
  not a lenient scorer. By class (hidden): argument/attribute 52/108 = 48%, name 23/57 = 40%,
  new feature 42/99 = 42%, other 28/51 = 55%, deprecation 12/13 = 92%.
  Cost of full run: ~98k tokens in, ~68k out (well under $0.25). All 99 envs built, 0 failures, 42 GB.
  A1 gate verdict: **consistent with the published baseline; passes**, with the caveat above.
  Re-check with `--library-fmt name` only if A3 also lands off the published 68%.
- **Env validity (2026-10-29):** `scripts/check_envs.py` scores the benchmark's reference
  solutions in our built envs: **324/328 pass**; broken: ids 36, 37, 41, 173 (e.g. gradio fails at
  import: `gradio_client.serializing` missing, transitive-dependency drift). Ceiling is 98.8%.
  Keep these four in the denominator for comparability with the paper, but note them.
- **A3 self-debug, FULL SET, gpt-4.1-mini, paper-faithful (1 round, visible-test trace only, Fig. 18):**
  hidden **183/328 = 55.8%** (CI +/-5.4), visible 218/328 = 66.5%; gap 10.7 pts (A1: 6.7), so the
  visible/hidden gap widens as published. Published: 68% hidden, 79.3% visible, i.e. we are ~12 pts
  short on both. A1 failed the visible test on 149/328 problems; all 149 were retried.
  Hidden by class A1 -> A3: argument/attribute 48% -> 50% (52 -> 54 of 108), name 40% -> 54%,
  new feature 42% -> 55%, other 55% -> 63%, deprecation 92% -> 92%. Self-debug helped argument/
  attribute changes least (+2 problems), which is the class PinPoint targets; n=108 and a +2
  difference are not significant on their own.
  Self-debug was ~126k tokens in / 27k out. Scoring needs `--score-workers 2` here (Docker gets
  ~3.8 GB; 6 workers OOM-ed).
  Variants (not in the paper's figure; reported as variants, the baseline stays 55.8%):

  | Arm | Hidden | Visible | Gap | arg/attr | name | new feat | other |
  |---|---|---|---|---|---|---|---|
  | A1 greedy | 47.9% | 54.6% | 6.7 | 48% | 40% | 42% | 55% |
  | A3 paper-faithful (1 round) | 55.8% | 66.5% | 10.7 | 50% | 54% | 55% | 63% |
  | A3 `--rounds 3` (variant) | 57.9% (CI +/-5.3) | 70.1% | 12.2 | 56% | 56% | 55% | 63% |
  | A3t `--show-test` (variant) | 62.2% (CI +/-5.2) | 77.4% | 15.2 | 57% | 60% | 62% | 69% |
  | Published A3 | 68.0% | 79.3% | 11.3 | | | | |

  Reading: showing the visible test source closes most of the gap to the published visible score
  (77.4 vs 79.3) but hidden is still ~6 pts low, and the visible/hidden gap grows to 15.2. The
  paper's self-debug is therefore probably more generous than Fig. 18 alone (test source in the
  prompt is the most plausible difference); this is a hypothesis, not confirmed. Extra rounds help
  little (+2 pts, 149 -> 102 still failing after round 3). Self-debug gains stay smallest on
  arg/attr in the paper-faithful run, but the variants narrow that. Differences between variants
  (~4-6 pts) are at or just beyond the CI width, so treat the ordering as suggestive.
  Variant cost: a few cents each. Gate verdict: A1 reproduced; A3 only reproduced approximately
  (variant, not baseline). The gate is treated as passed on A1 with A3 as a documented discrepancy.
- **A2 docs-RAG, FULL SET, gpt-4.1-mini (2026-10-29):** `harness/gc_docs.py` + `gc_runner.py rag`.
  Corpus: 207 doc URLs from the dataset `docs` field; 181 live, 24 recovered (19 via Wayback
  snapshots, a few via following meta-refresh stubs on moved sympy/matplotlib pages), 2 lost
  (networkx 2.4/2.5, so problems 31 and 32 get the plain A1 prompt). Caveat: recovered librosa/pandas
  pages are 2025-26 snapshots and may not match the pinned version. text-embedding-3-large (~1.65M
  tokens, ~$0.21), chunk 1500 chars / 200 overlap and query = problem text are MY assumptions
  (paper specifies only the embedding model and k in {1, 3}); retrieval is restricted to the
  problem's own pages. Docs are appended to the A1 user prompt in a `<documentation>` block.

  | Arm | Hidden | Visible | Gap | arg/attr | name | new feat | other |
  |---|---|---|---|---|---|---|---|
  | A1 | 47.9% | 54.6% | 6.7 | 48% | 40% | 42% | 55% |
  | A2 k=1 | 49.1% (+/-5.4) | 56.1% | 7.0 | 51% | 42% | 41% | 57% |
  | A2 k=3 | 49.4% (+/-5.4) | 57.0% | 7.6 | 54% | 44% | 42% | 49% |

  Reading: retrieved docs add about +1.2 to +1.5 pts hidden, far inside the CI, so A2 is
  indistinguishable from A1 here. That fits the thesis (docs alone are weak at fixing version
  errors) but is not proof; the retrieval setup is my own. Dev-subset A2 k=3 looked worse (36% vs 46%,
  n=50), which the full set shows was noise. A2 and A1 results are both far below A3, so self-debug
  remains the baseline to beat. Cost of generation: ~380k tokens in per arm.
- **Keys (2026-10-28):** OpenAI works (credit present). Groq key works but Groq now hosts no
  Llama 3.x chat model (only gpt-oss, qwen3.8, prompt-guard). OpenRouter key valid with $0 credit.
  So the baseline gate runs on **gpt-4.1-mini via OpenAI**; Llama 3.1 needs OpenRouter credit.
- **Open assumption to verify against A1:** the library version is rendered as `name==version`
  in the user prompt (`--library-fmt pinned`); the paper's Fig. 17(c) only shows a `library` tag.
- `.claude/settings.local.json` (gitignored) allows `docker run/volume/images/ps/info/pull`.

**Open items / discrepancies**
- The paper text read so far gives **no percentage error taxonomy** (only: AssertionError and
  TypeError most common; self-debug cuts every class 50–90%). The "wrong parameters = 26.6%"
  and "66.36% with correct docs" figures come from *When LLMs Lag Behind* (2604.09515),
  not GitChameleon, and are on a different benchmark with mostly small models; see
  docs/01-related-work.md. Still read GitChameleon's unread 73k chars and appendices.
- Our error-class table (section 4) therefore has no published GitChameleon numbers to
  compare against. We must classify failures ourselves (from tracebacks), which is also the
  only way to get MISSING/RENAMED/SIGNATURE labels.
- ~~Prompt templates~~ now captured above. Still unresolved: **Llama 3.1 "Turbo" size**
  (Appendix J lists no parameter count and its citation points to an unrelated 8B security
  model, so this looks like a bibliography slip). Together AI's "Turbo" naming is a hosted
  variant; treat the size as unknown until we see which endpoint reproduces ~30%.
- Docker on Windows 11 Home means Docker Desktop + WSL2. Verify it runs the harness image
  before week 3; otherwise run execution on Kaggle/Linux.
- The agent/assistant results (≈55% sandbox agent) are not comparable to single-shot arms.

**Model shortlist (decision pending):**
1. **Llama 3.3 70B Instruct** (36.3 greedy). Open weights, usually has a free OpenRouter
   endpoint, published greedy number. Headroom is large. Has no published self-debug or RAG
   numbers, so only A1 is directly reproducible.
2. **Llama 3.1 Instruct** (30.2 → 52.1 self-debug). Only Llama with published greedy *and*
   self-debug, so A1 and A3 are both reproducible. Confirm which size "Turbo" refers to.
3. **GPT-4.1-mini** (44.2 → 68 self-debug). Paid but cheap per run. Strongest published
   anchor for A1 and A3. Estimate cost before choosing; 3 seeds × 5 arms adds up.
Recommendation: Llama 3.1 for the reproducibility gate (two anchors, free), GPT-4.1-mini as a
second model only if budget allows.

## 3. Main results table (slide 4)

| Arm | Visible | **Hidden** | Hidden−Visible gap |
|---|---|---|---|
| A1 Greedy | | | |
| A2 Docs-RAG | | | |
| A3 Self-debug | | | |
| **A4 PinPoint** | | | |
| A5 PinPoint + self-debug | | | |

**The gap column is as important as the score.** GitChameleon found the visible/hidden gap
*widens* after self-debugging — fixing the shown test doesn't transfer. If introspection
narrows it, that's a mechanistic result, not just a bigger number.

## 4. The breakdown that makes the case

Success rate **by error class**:

| Error class | A2 Docs-RAG | A3 Self-debug | **A4 PinPoint** |
|---|---|---|---|
| Symbol removed / renamed | | | |
| Symbol moved | | | |
| **Signature / parameter change** | | | **← your win** |
| Deprecated but working | | | |

Published context: wrong parameters are 26.6% of execution failures, and REPLACEAPI does
name substitution only. If PinPoint wins here and ties elsewhere, the story is clean and
honest — you fixed the class nobody could.

## 5. Secondary metrics

- **Repair iterations to success** (efficiency vs self-debug)
- **Introspection failure rate** — how often `inspect.signature` can't resolve (C
  extensions, decorators). Report it; it's an honest limitation and a future-work hook.
- **False-repair rate** — correct code that PinPoint changed and broke. Critical: a tool
  that damages working code is unusable.
- **Latency per request** (vs REPLACEAPI's published 1.83–3.31s/sample)

## 6. The private-library experiment (the memorable one)

Build a small synthetic "internal SDK": ~15 functions, realistic docstrings, **never
published anywhere**. Generate version v1 and v2 with renames, moved symbols, and
signature changes.

| Method | Can it work? | Why |
|---|---|---|
| Docs-RAG | ✗ | nothing to retrieve |
| Weight editing | ✗ | no training data |
| Self-debug | partial | errors only, no contract |
| **PinPoint** | ✓ | the object is right there |

This is a *structural* argument, not an empirical one — which makes it stronger. Run it
anyway for the numbers, but the slide works on the logic alone.

## 7. Ablations

Strip one probe at a time — signature only / namespace search only / deprecation capture
only — to show which source carries the result. Cheap (reuses cached generations) and it
converts a system into a finding.

## 8. Cost plan

| | |
|---|---|
| OpenRouter 10-credit unlock → 1000 free req/day | **$10** |
| Ollama local (dev loop) | $0 |
| Kaggle T4×2, 30h/week (batch runs) | $0 |
| Docker execution, introspection | $0, CPU |
| AWS | unspent |

**Discipline:** develop on a 50-problem subset. Full 328 only for final numbers. Cache
every generation. You will iterate 20+ times — nineteen of those don't need the full set.

## 9. Statistics

Run 3 seeds per cell. Report mean ± std. Paired bootstrap over problems for arm-vs-arm
differences — same problems across all arms, so pair them.

## 2b. Probe + resolver + diff validation (2026-10-29)

Code: `src/pinpoint/{probe,resolve,diff}.py`; scripts `validate_probe.py`, `eval_diff.py`; 28 offline tests.

- **Probe in the real pinned envs:** 300 of 306 importable-root API names from the reference
  solutions resolve `ok`; the 6 `missing` are garbled paths in the dataset's `api_calls` labels
  (e.g. `tornado.ioloop.ioloop.IOLoop.current`), not probe errors (my reading of the paths).
  The first run found a real bug: 18 Python 3.7 envs could not parse `list[str]` (fixed with
  `from __future__ import annotations`).
- **Diff vs known outcomes (gpt-4.1-mini, all 328, non-stdlib roots only):**
  - DEPRECATED is **not an error signal**: 26 of 328 *correct* reference solutions are flagged,
    because the benchmark deliberately uses APIs deprecated in the pinned version. It is kept as
    informational context, never a repair trigger. (Import-time warnings are no longer attributed
    to objects: they flagged 100 reference solutions, mostly geopandas->shapely noise.)
  - RENAMED / MISSING / MOVED / SIGNATURE on the **reference solutions: 0 false alarms** after
    two fixes (MOVED only for module parents; no verdict on chains through instance attributes).
  - On **A1 answers: 28 problems flagged, 27 of them fail hidden tests (96%)**; 9 problems have a
    SIGNATURE issue and all 9 fail. So the flags are precise.
  - **Recall is low: 27 of 171 failing A1 answers (16%)** have a statically detectable name or
    signature error. Most A1 failures are semantic/behavioural, not visible to signature checks.
    This is the upper bound on what an introspection-only repair can reach on this model, and it
    bears directly on the week-6 criterion (<3 pts over self-debug). Honest expectation: A4 over A1
    is capped near +16 pts of failing answers x the fraction the repair actually fixes.
  - A3 (self-debug) answers have only 3 such flags left: self-debug already removes most
    detectable name errors, so PinPoint's marginal value over A3 must come from the remainder
    and from the signature class.

## 2c. PinPoint arms (A4, A5), gpt-4.1-mini, all 328 (2026-10-29)

`harness/gc_pinpoint.py`: per turn resolve -> probe in the pinned venv -> diff -> repair prompt quoting the
installed signature / existing names -> repeat (max 3 turns, stop when the diff is clean). DEPRECATED never
triggers a repair. Hidden tests are not used inside the loop. A4 = on top of A1, A5 = on top of A3.

- **First pass (v1)** found one false repair (#4): the model had written correct feature-detection
  (`try: torch.special.i0 ... except AttributeError: <scipy fallback>`), the diff flagged the guarded access,
  and the repair replaced it with `torch.i0`, which failed hidden tests. v1: A4 51.5% (fixed 13, broken 1),
  A5 57.9% (fixed 8, broken 1).
- **Fix made AFTER seeing v1 results (post hoc, disclosed):** uses inside a `try` whose handler catches the
  relevant error (AttributeError/ImportError for missing names, TypeError for signatures, or bare/Exception)
  are not judged. Principled (explicit feature detection) but motivated by one observed case.
- **v2 (final):** A4 **170/328 = 51.8%** hidden (CI +/-5.4), visible 58.5%; vs A1 47.9%: **fixed 13, broken 0**
  (net +13, +4.0 pts). Fixed ids: 32, 51, 99, 125, 199, 252, 257, 260, 277, 299, 303, 311, 312.
  Turn 1 flagged 29 problems (10 RENAMED, 14 SIGNATURE, 2 MOVED, 8 MISSING); 5 after turn 2; 1 after turn 3.
  Cost: ~24k tokens in total across turns (cents).
- A4 (51.8) is still below plain self-debug A3 (55.8): introspection alone does not beat execution feedback.
- **A5 (v2, on top of A3):** **191/328 = 58.2%** hidden (CI +/-5.3), visible 68.9%, gap 10.7; vs A3 55.8%:
  **fixed 8, broken 0** (net +8, +2.4 pts). Fixed ids: 98, 99, 197, 199, 216, 252, 260, 311. Turn 1 flagged 16
  (6 RENAMED, 6 SIGNATURE, 4 MISSING, 1 MOVED); 6 after turn 2; 2 after turn 3.
  By class A3 -> A5 (hidden): arg/attr 50% -> 53%, name 54% -> 56%, new feature 55% -> 59%, other 63% -> 63%.
- **Summary table (gpt-4.1-mini, 328, hidden):** A1 47.9 | A2 k=3 49.4 | A4 51.8 | A3 55.8 | A5 58.2.
  Single seed; paired fixed/broken counts are 13/0 and 8/0, but the unpaired CIs (+/-5.3) overlap, so the
  A5-over-A3 margin (+2.4) is below the week-6 threshold of 3 pts. Not yet evaluated: 3 seeds, signature-class
  breakdown vs A3, a second model.
- **v3 (rerun with annotation-aware resolver + member listing; 2026-10-29).** Kept beside v1/v2, not replacing them.
  - A4: **172/328 = 52.4%** hidden (CI +/-5.4), visible 58.8%; vs A1: **fixed 15, broken 0**. Turn 1 flagged 33
    (13 RENAMED, 15 SIGNATURE, 2 MOVED, 8 MISSING); 4 after turn 2; 0 after turn 3.
  - A5: **190/328 = 57.9%** hidden (CI +/-5.3), visible 68.3%; vs A3: **fixed 7, broken 0** (+2.1 pts).
    Fixed ids: 98, 197, 199, 216, 252, 260, 311. Turn 1 flagged 21; 5 after turn 2; 1 after turn 3.
  - Reading: A4 gains slightly (+4.5 over A1, 15/0). A5 moved from +2.4 (v2) to +2.1 (v3): the extra resolver
    coverage did not help on top of self-debug, and problem 99 (fixed in v2) is no longer fixed. Both stay under
    the 3-point week-6 line. The honest summary for A5 is "+2 to +2.4 over A3, never hurts (0 broken in all
    versions), too small to claim on one seed". Seeds and the signature-class breakdown are next.
- **Signature-class breakdown (roadmap step 2; scripts/sig_breakdown.py).** Of the 21 A3 answers with a verified
  finding, A3 passed 1 hidden test set and A5 passed 8 (fixed 7, broken 0). By kind (A3 pass -> A5 pass):
  SIGNATURE 0/6 -> 4/6, RENAMED 1/9 -> 3/9, MOVED 0/1 -> 1/1, MISSING 0/5 -> 0/5 (kinds overlap per problem).
  So the "signature-class edge" exists: the gain concentrates where the installed API contradicts the code, and
  MISSING (no replacement exists) is not fixed. This condition is met; the +3-pt overall condition is not.
  Caveat: 21 problems, one seed, and findings were computed on A3 answers before reading hidden results.

## 2d. Private-library case study: invented SDK `halyard` (2026-10-29)

`experiments/private_sdk/` (library, 24 tasks, `docs.md`, `run.py`). An invented job-queue SDK that no model has
seen and no public docs describe. It is a **case study, not a benchmark** (24 tasks, one library, written by me,
fixed and verified before any model ran: every reference passes its tests, no bare stub passes the visible test).
gpt-4.1-mini, greedy, local scoring. Hidden tests never used inside any loop.

| Arm | Hidden | Visible |
|---|---|---|
| P1 no help | 1/24 | 1/24 |
| P2 hand-written API reference in the prompt | **24/24** | 24/24 |
| P3 self-debug (visible-test trace) | 2/24 | 3/24 |
| P4 PinPoint on P1, v1 (names + spelling-close candidates) | 4/24 | 5/24 |
| P5 PinPoint on P3, v1 | 3/24 | 5/24 |
| P4 PinPoint on P1, v2 (+ members the installed parent really exposes) | **11/24** | 11/24 |
| P5 PinPoint on P3, v2 | **14/24** | 15/24 |

Paired v2: P4 vs P1 fixed 10, broke 0; P5 vs P3 fixed 12, broke 0.

- **v1 -> v2 was a post-hoc change, made after seeing v1.** v1 findings for a missing method said "no similarly
  named symbol exists", which tells the model nothing. v2 adds `inspect.getmembers`-style evidence: the installed
  parent's public members with signatures (the thesis's own tool, previously under-implemented). Because it was
  chosen after looking at failures on these same 24 tasks, treat v2 as development-set performance; confirming it
  needs fresh tasks (not done).
- **What it shows:** with no docs and no help a model cannot use an unseen SDK (1/24); self-debug barely helps
  (2/24) because the trace says `AttributeError` without saying what exists; introspection raises it to 11-14/24
  and removes every statically detectable error (0 verified errors left), at zero documentation cost.
- **What it does not show:** introspection does not match written docs (24/24). After repair the code uses real
  names and signatures but still gets semantics wrong (return shapes, what `nack` does after max attempts,
  de-duplication rules), which signatures do not convey. Docstrings are the natural next evidence
  (`inspect.getdoc`) but are effectively documentation shipped in the code; not tried, to avoid more tuning on
  this task set. Claim to make: "recovers roughly half of what written docs give, when no docs exist", not
  "replaces docs".
- Resolver now also follows annotated parameters (`client: halyard.Client`); the GitChameleon A4/A5 numbers in
  2c were produced before that change and have not been rerun.

### 2c-seeds. Three seeds (roadmap step 3; scripts/run_seed.sh, scripts/bootstrap.py)
Seed 0 is greedy (temperature 0, v3 numbers above); seeds 1 and 2 use temperature 0.3. Same model, all 328 problems, hidden tests.

| seed | A1 | A3 | A4 | A5 |
|---|---|---|---|---|
| 0 | 47.9 | 55.8 | 52.4 | 57.9 |
| 1 | 50.3 | 56.7 | 54.6 | 59.5 |
| 2 | 48.2 | 55.5 | 51.8 | 58.5 |

Pooled per-problem difference, 10,000-resample paired bootstrap over problems (95% CI):
A4-A1 **+4.17 [+2.34, +6.20]**; A5-A3 **+2.64 [+1.22, +4.37]**; A3-A1 +7.22 [+4.88, +9.76]; A5-A4 +5.69 [+3.35, +8.13].
PinPoint never broke a problem in the seed 1 runs (0 broken in both arms). The A5 gain is positive and its CI excludes 0,
but the point estimate (+2.6) is still just below the week-6 3-pt line and the CI includes it. Caveats: three seeds of one
model; seeds 1-2 differ only by sampling; the bootstrap resamples problems, not models or benchmarks.

### 2d-heldout. Held-out private-SDK tasks (roadmap step 4; experiments/private_sdk/tasks_heldout.py)
24 NEW tasks on the same invented `halyard` 2.3.0, written after the PinPoint code (src/pinpoint/*, harness/gc_pinpoint.py)
was frozen (hashes: experiments/private_sdk/FREEZE_before_heldout.txt) and before any model saw them; run once, gpt-4.1-mini,
greedy, no changes afterwards. References pass and stubs fail (check_refs.py). The only edit after freezing was
making run.py/check_refs.py accept `--tasks` (task-module selection and output-file suffix); no PinPoint logic changed.

| Arm | Hidden | Visible |
|---|---|---|
| P1 no help | 2/24 | 3/24 |
| P2 written docs | 22/24 | 23/24 |
| P3 self-debug | 3/24 | 4/24 |
| P4 PinPoint on P1 | **9/24** | 9/24 |
| P5 PinPoint on P3 | **11/24** | 12/24 |

Paired: P4 vs P1 fixed 7, broke 0; P5 vs P3 fixed 8, broke 0. Dev set (v2) was 11/24 and 14/24, so the held-out number is
a few tasks lower, as expected for a tuned dev set, and the picture is unchanged: ~half of what written docs give
(22/24) when no docs exist, from 2-3/24 without help. One run, one model, 24 tasks, an invented library: a case study, not a benchmark.
Turn 1 flagged 13 (P4) and 19 (P5) answers, mostly MISSING names; all clean after 2 turns.

### 2e. Second model (roadmap step 5; gpt-4o-mini, bounded cost)
- **Held-out halyard tasks (24), hidden:** P1 3 | P2 docs 18 | P3 self-debug 5 | P4 7 (fixed 4, broke 0) | P5 12 (fixed 7, broke 0).
  Same direction as gpt-4.1-mini (2 / 22 / 3 / 9 / 11).
- **GitChameleon dev subset (50 problems only, to bound cost), hidden:** A1 24.0 | A3 30.0 | A4 24.0 | A5 30.0.
  PinPoint flagged 5/50 answers at turn 1 and cleared them by turn 3, but **fixed 0, broke 0** on both bases.
  So on GitChameleon the second model shows no measurable effect: 50 problems (CI +/-12) and ~5 flags cannot detect a
  +2-4 pt effect either way. This does NOT confirm the GitChameleon gain on another model; it only shows no harm.
  Honest status of C6: confirmed on the private-library study, inconclusive on GitChameleon.

### 2f. Ablation: which evidence does the work? (roadmap step 6; experiments/private_sdk/ablate.py)
Same detection, same 24 held-out halyard tasks, gpt-4.1-mini; only the text of the findings changes. Hidden passes /24:

| Findings given to the model | base P1 | base P3 |
|---|---|---|
| (no PinPoint) | 2 | 3 |
| L0 names only ("`x` is wrong for the installed version") | 3 | 3 |
| L1 + what is wrong + "did you mean" suggestions | 4 | 5 |
| L2 + installed signatures | 3 | 4 |
| L3 full PinPoint (+ members the installed parent exposes) | 7 | 10 |

- The big step is L3, the member listing (what the installed object really exposes): 3-5 -> 7-10. Saying only *that* something is wrong
  (L0) or even naming the error (L1/L2) barely helps; the model needs the list of real names to choose from.
- Sampling noise is real: the identical L3 prompts scored 9/11 in the section 2d-heldout run and 7/10 here (API output is not
  bit-reproducible at temperature 0, and arm names make fresh calls). Read differences of +/-2 as noise; the L0-L2 vs L3 gap is larger than that.
- Docstrings (closest to documentation) were not added: the probe does not extract them, and P2 (written docs, 22/24) already
  marks that end of the scale. Single model, 24 tasks.

### 2g. Shipped tool (roadmap step 7)
`pinpoint check FILE [--python P] [--path DIR] [--json]` and `pinpoint repair FILE [--model M] [--turns N] [--write]`
(src/pinpoint/{check,repair,cli}.py; `pip install -e .` provides the command). Same resolver, probe, diff and the same
repair prompt/findings text as the experiments (tests/test_cli.py asserts the prompt matches harness/gc_pinpoint.py).
Demo: examples/broken_halyard.py -> 3 verified findings -> `repair` fixes all three in 2 turns (one fix, `ttl`->`delay`, is a
plausible guess the tool cannot verify semantically; the diff is shown and `--write` is opt-in). 42 tests pass.
