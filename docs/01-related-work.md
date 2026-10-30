# PinPoint — Related Work

**Rule: week 1, before any code. If you cannot honestly write the positioning paragraph
at the bottom, the project changes — not the paragraph.**

---

## The five papers

| # | Paper | What it is | Key numbers | Why it isn't you |
|---|---|---|---|---|
| 1 | **GitChameleon 2.0** ([2507.12367](https://arxiv.org/pdf/2507.12367)) | Benchmark: 328 manually authored version-conditioned Python problems, assertion tests, clean Docker per problem | Greedy ~48–51% hidden. Self-debug: Llama 3.1 30→52.1, GPT-4.1-mini 44→68, best 70.4. RAG k=3: GPT-4.1 48.5→58.5. Sandbox agent ~55% | **Your eval set.** Execution feedback already done — don't claim it. But: no runtime introspection anywhere, and the visible/hidden gap *widens* after self-debug |
| 2 | **When LLMs Lag Behind** ([2604.09515](https://arxiv.org/html/2604.09515v1)) | 270 real API updates, 8 libraries, 11 models | With full docs: adoption 92.87%, **executable 66.36%**. Omission = 42.1% of adoption failures. Wrong params = 26.6% of execution failures | **Your headline motivation.** Benchmark + study only, no fix. Models get no runtime feedback during generation |
| 3 | **LibEvolutionEval** ([2412.04478](https://arxiv.org/pdf/2412.04478)) | Benchmark + version-aware RAG study | Mistral-7B PyTorch 65.8→67.6, Matplotlib 60.18→69.05; GPT-4o-mini PyTorch 64.3→70.14 | Static version resolution: requirements.txt, dependency matrices, scraped docs. **No runtime inspection.** RAG doesn't remove version bias |
| 4 | **LLMs Meet Library Evolution** ([2406.09834](https://arxiv.org/html/2406.09834)) | Study + 2 fixes: REPLACEAPI (decoding-time), INSERTPROMPT | DUR 25–38%, up to 70–90% on outdated-context prompts. REPLACEAPI FR 85.2–99.6%, INSERTPROMPT FR 25.7–97.2% | AST + manually collected doc/changelog mappings. REPLACEAPI is **name substitution only**. Their own future work asks for exactly what you're building |
| 5 | **Model editing for deprecated APIs** ([2511.21022](https://arxiv.org/html/2511.21022)) | AdaLoRA-L weight editing vs 10 editing methods | Qwen2.5-Coder: Effectiveness 98.2, Portability 74.3, Specificity 88.1 | Edits weights, one API at a time. **No signature-change evaluation.** No retrieval or execution-feedback baselines compared |

## The confirmed gap

Read across all five: every approach grounds itself in **documentation, changelogs, or
static analysis**. None introspects the installed package at runtime.

Three consequences you can exploit:
1. **Signature changes are unhandled.** Name replacement can't fix them; editing doesn't
   test them; wrong parameters are the biggest execution-failure class (26.6%).
2. **Execution feedback doesn't transfer.** GitChameleon's visible/hidden gap widens after
   self-debugging. Introspection gives the *contract*, not one passing case — it should
   generalise where self-debug doesn't. **That is a testable mechanistic prediction.**
3. **Private libraries break every existing method.** No docs to retrieve, no training
   data to edit. Introspection is unaffected.

## Week-1 reading, with the question each must answer

| # | Paper | Question |
|---|---|---|
| 1 | GitChameleon 2.0 | Which models have published baselines, and is one available on a free tier? Exactly how is the Docker harness set up — can I reuse it? |
| 2 | When LLMs Lag Behind | Full breakdown of the 26.6% parameter errors — what do they look like? These are your target cases |
| 3 | LLMs Meet Library Evolution | How exactly does REPLACEAPI regenerate arguments? Is it a baseline I can run? |
| 4 | LibEvolutionEval | Anything reusable in their version-resolution pipeline? |
| 5 | Model editing | Skim. Cite as the weights-based alternative, note the missing signature evaluation |

### Week-1 reading results (2026-10-28)

Read via arXiv HTML (papers 2, 3, 4, 5 mostly in full; the last 1–12k chars of 4 and 5 and
paper 1's appendices unread). Paper 3's PDF would not extract, so its HTML was used.

| # | Answer to the question | Consequence |
|---|---|---|
| 2 | The 26.6% is "Wrong Parameters" among **781 execution failures** under the *best* prompt (UD+Doc+CoT+SR). Incorrect API usage is 52.1% of failures; **47.9% are not update-related** (syntax, implementation). Hallucinated behaviour 16%. P2 "modification" (name/param/return changes) is 128 of 270 and the hardest pattern; 43.4% of P2 adoption failures are parameter-level omission. **No concrete wrong-parameter example given.** Models are mostly small open ones (DeepSeek-Coder, CodeLlama, R1-distill) + GPT-4o mini. Labels by GPT-5 mini (90% on 50 failure labels). Data: `AhmedNusayer/knowledge-conflict-codegen` | The 26.6% is of failures *after* docs, not of all failures, and about half of the remaining failures introspection cannot touch. Cite precisely. The 66.36% is for small models; do not generalise it to frontier models |
| 3 | Fully static: tree-sitter ASTs, versions from `requirements.txt` + dependency matrix, docs scraped from websites. Line-level completion, F1 on API match. Version-aware *prompt comment* adds only ~0.3–1 pt; version-aware RAG (top-3 docs) adds 2–14 pts. No code/data link found in the text | Nothing reusable for the harness. Useful only as a number: a bare "version = X" hint is nearly worthless, and GitChameleon already puts the version in the prompt |
| 4 | REPLACEAPI: needs a hand-collected deprecated→replacement map (145 entries); at decoding time cuts the completion at the deprecated API, appends the replacement tokens, lets the LLM regenerate the suffix (args). Greedy, 50-token cap. **Cannot run on black-box API models** (they say so). Replication package is on an anonymous 4open.science link, runnability unconfirmed. Future work lists "parameter-level" deprecations as an uncovered case, not introspection | **Not a runnable baseline** for us (OpenRouter models, no decoding control). Treat as a conceptual comparator, or build a docs-mapping/name-substitution arm ourselves if wanted. Soften "their future work asks for exactly what you're building" to "they exclude parameter-level changes" |
| 5 | AdaLoRA-L edits a split of layers on 1.3–3B models; EDAPIBench = 82 mappings, 8 libraries, >3k instances, **single-line completion only**. Signature changes **not evaluated**; they admit it produces valid calls with mismatched arguments and assert (untested) that it suits signature changes. Only external baseline is REPLACEAPI, which beats it on Portability (>96% AEM). Code: `GuanchengLin/EDAPIBench` | Cite as weights alternative, as planned. Their own limitation text supports our signature-class argument |

**Net effect on the thesis:** the gap survives (nobody uses live signatures), but two
motivating numbers need rewording (see brief §1), and no external method is a ready-to-run
baseline. Our comparison arms are the ones we build: A2 docs-RAG, A3 self-debug, plus
GitChameleon's own published numbers.

**Also search explicitly for:** `inspect.signature` + LLM code repair, runtime introspection
code generation, API contract grounding. If someone built this, find out in week 1.

## Scoop log

| Date | Paper | Threat | Action |
|---|---|---|---|
| 2026-10-28 | **Empirical Analysis of Static Analysis Methods for Detection and Mitigation of Code Library Hallucinations** ([2604.07755](https://arxiv.org/abs/2604.07755), Miranda-Pena et al.) | **Medium — closest found.** Builds a grammar from per-library docs using `inspect` (docstrings → JSON), plus Mypy/Pyright; catches wrong parameter names in part. Full HTML read: the grammar is built by running `inspect` over each target library to extract **docs and signatures** into JSON → GBNF (build-time, used for post-hoc detection or constrained decoding). So signature-level introspection is *not* new. Differences: hallucination-focused, not version-conditioned; static grammar, no repair loop that puts the real signature in the prompt; misses `from x import y` and atypical aliases; static detection only 14–85%, grammar ≤ ~11%; repair gains inconsistent; no discussion of library versions | Cite as nearest neighbour and as a *baseline family* ("introspection-derived grammar"). Do not claim "first to use `inspect`" — claim version-conditioned repair loop + GitChameleon + private SDK |
| 2026-10-28 | **Understanding and Mitigating Library-Related Issues in LLM-Generated Code** ([2610.00622](https://arxiv.org/html/2610.00622v1)) | Low–medium. Validates code in the execution env, but cross-references a *documentation bundle*; no `inspect.signature`, no signature checks. Lists "version-aware reasoning" as future work | Cite as env-validation + docs. Full text read: no introspection, no version-awareness |
| 2026-10-28 | **DeepGroundRepair** ([2610.16897](https://arxiv.org/abs/2610.16897)) | Low. Docs database for grounding; `importlib`/`getattr` only for API *existence*; deep-learning shape errors; not version-aware | Cite as docs-grounded repair |
| 2026-10-28 | Blog: *The Deprecated API Trap* (tianpan.co, 2026-04-17) | Low as research, but **prior idea**: inject `inspect` signatures/docstrings from installed packages into the prompt. Unevaluated | Cite as folk practice; your contribution is the evaluation, error-class breakdown and repair loop |
| 2026-10-28 | *Evaluating Incompatible Third-party Library API Usage in LLM-based Code Completion* ([doi 10.1145/3830085](https://doi.org/10.1145/3830085)) | Unknown — ACM page returned 403, abstract not read | Find an open copy (arXiv/author site) or read via institutional access |

**Verdict (2026-10-28, web search only, not exhaustive):** no paper found that repairs
version-conditioned code using live signatures from the installed package and evaluates it
on GitChameleon. Week-1 kill criterion not triggered. **But** the claim "none introspects
the installed package" is only safe for the five core papers; partial runtime checks exist
elsewhere (`importlib`/`getattr` existence checks, `inspect` for docstrings). Soften "first"
to "first to ground repair in live signatures and evaluate on version-conditioned
benchmarks."

## The positioning paragraph (draft, revise weekly)

> Prior work on version-correct code generation grounds the model in documentation —
> retrieved (LibEvolutionEval), injected (INSERTPROMPT), substituted at decoding time
> (REPLACEAPI), or baked into weights (AdaLoRA-L). Documentation is not enough: in one
> study with mostly small open models, supplying the full correct docs lifted the
> executable rate only to 66.36%, and wrong parameters were the largest update-related
> failure class (26.6% of remaining failures). Execution feedback helps but fixes the
> visible case rather than the contract: on GitChameleon 2.0 the visible/hidden gap widens
> after self-debugging for every model tested (Llama 3.1: 7.9 → 17.1 points).
> Concurrent work validates code against the environment or builds grammars from
> `inspect`-derived docstrings, but checks existence or docs, not live signatures, and is
> not evaluated on version-conditioned problems.
> We instead ground repair in runtime introspection of the installed package, which is
> exact by construction, targets the signature-level errors that name substitution cannot
> reach, and applies unchanged to private libraries where no documentation or training
> data exists.
