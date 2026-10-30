# PinPoint — The Full Story

One page to re-read at the start of any session. Detail lives in the numbered docs.

## What and why
LLMs write code against the library version in their training data; you run a different one
(`df.append()` was removed in pandas 2.0). Every published fix feeds the model
**documentation** (RAG, prompt injection, decoding-time name substitution, weight editing)
or execution errors. Even with complete correct docs only 66.36% of generated code
executes, and wrong parameters are 26.6% of execution failures.

**PinPoint** reads the answer off the *installed object* instead: `inspect.signature`,
`typing.get_type_hints`, `inspect.getmembers`, captured `DeprecationWarning`s. It checks
generated code against that, repairs it with the real signature in the prompt, and verifies.

## Constraints
12 weeks · ~$10 · no GPU · Python only · no new benchmark · no weight training.
Output: working tool + 5-slide presentation (paper optional).

## The bets
1. Introspection beats docs as a repair oracle, especially on **signature/parameter** errors.
2. It narrows the visible/hidden gap that self-debugging widens.
3. It works on **private libraries** where Docs-RAG and weight editing structurally cannot.

## Where we are (update at each milestone)
- 2026-10-28 — Week 1. Project scaffolded; folder renamed `pinpoint`.
- Scoop check done (web search, non-exhaustive): no paper found doing version-conditioned
  repair from live signatures. Nearest: Miranda-Pena et al. 2604.07755, which uses `inspect`
  to build a signature/docs grammar for hallucination detection (not version-aware, no
  repair loop). **Consequence: do not claim "first to introspect"; claim the repair loop +
  version-conditioned evaluation + private-library result.** Details in `01-related-work.md`.

## Next
1. Read the five core papers against their target questions (`01-related-work.md`).
2. Pick a model with a published GitChameleon 2.0 baseline that is free-tier.
3. Harness + SQLite cache + resumable runner, 50 problems end to end (week 2).
4. Reproduce a published baseline (weeks 3–4) — **the go/no-go gate.**

## Rules of engagement
- Phase rule: no probe / repair loop until week 5+.
- Cache every generation; develop on 50 problems; full 328 only for final numbers.
- Kill criteria are in `00-brief.md` §6 — honour them.
