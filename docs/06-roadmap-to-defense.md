# Roadmap to a defensible project (written 2026-10-29)

Goal: a project whose every claim survives "how do you know?". Order matters: do one step at a time,
finish it, record it in docs/03-eval-plan.md, then move on.

## Claims we intend to make (and the evidence each needs)

| # | Claim | Evidence needed | Status |
|---|---|---|---|
| C1 | Our harness reproduces published GitChameleon numbers | A1 within a few pts; A3 explained | A1 yes (47.9 vs 44.2); A3 approx (55.8 vs 68), documented |
| C2 | Introspection findings are precise (no false alarms on correct code) | diff run on reference solutions | 0 false alarms outside DEPRECATED; done |
| C3 | Introspection repair adds a small, consistent gain on GitChameleon | 3 seeds, paired bootstrap, A4/A5 vs A1/A3 | 1 seed: +4.0 / +2.4, 0 broken; rerun pending |
| C4 | Only ~16% of failures are visible to introspection (the ceiling) | A1 failures vs flagged | done, reported as a limitation |
| C5 | With no docs, introspection recovers much of what a model cannot do alone | fresh held-out tasks on an unseen SDK | v2 tuned on dev tasks; needs held-out set |
| C6 | It works on more than one model | second model on GitChameleon + SDK | not done |
| C7 | It is usable as a tool | pip-installable wrapper + demo | not done |

## Steps, in order

1. **Rerun A4/A5 on GitChameleon** with the annotation-aware resolver and member listing (running).
   Keep v1 / v2 / v3 numbers side by side; do not overwrite.
2. **Signature-class breakdown**: A3 vs A5 on SIGNATURE / RENAMED / MISSING problems only (the second week-6 condition).
3. **Seeds**: 3 seeds for A1, A3, A4, A5 (temperature 0 is near-deterministic, so use temperature 0.3 with
   different seeds, and state that plainly). Paired bootstrap CIs for A5-A3 and A4-A1.
4. **Held-out SDK tasks**: write 24 NEW tasks against `halyard` (or a second invented SDK) AFTER freezing
   the PinPoint code. Run once. Report this as the headline private-library number; the dev-task number is secondary.
5. **Second model**: a cheap different model (e.g. an OpenAI smaller/larger variant) on SDK tasks and on the
   GitChameleon dev subset; full set only if budget allows.
6. **Ablation on the SDK study**: names-only vs +signatures vs +member listing vs +docstrings (the last being
   closest to documentation). This answers "what part of introspection is doing the work?".
7. **Tool**: `pinpoint check file.py` (CLI) that reports findings against the active environment, and a
   `pinpoint repair` that calls a model. Package metadata in pyproject, README usage, small demo script.
8. **Write-up and 5 slides**: problem, idea, how it works, honest results (incl. limits), demo.

## Defence checklist (questions we must be able to answer)

- Why is your A3 lower than the paper's? (unspecified self-debug details; variants measured: 57.9 with 3 rounds, 62.2 with test source)
- Did you tune on the test set? (post-hoc changes are disclosed in 03-eval-plan §2c/§2d; held-out SDK tasks fix this)
- Is +2.4 significant? (paired fixed/broken counts and bootstrap, not the overlapping unpaired CI)
- What does it NOT fix? (semantic errors; ~84% of GitChameleon failures; it does not replace docs)
- Could the SDK have been rigged to favour you? (fixed before runs; docs arm reaches 24/24 so tasks are solvable; the SDK's naming is conventional)
- Cost? (a few cents per arm; scoring time dominates)
