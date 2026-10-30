# PinPoint — Timeline and Slide Map

---

## 12 weeks

| Week | Work | Shippable |
|---|---|---|
| 1 | Read all five papers. Write the positioning paragraph. Search explicitly for prior introspection-based repair | `01-related-work.md` filled in |
| 2 | GitChameleon harness running. Pick the model (must have a published baseline). Caching layer + resumable runner | can run 50 problems end to end |
| **3–4** | **Reproduce a published baseline within a few points** | **GO / NO-GO** |
| 5 | Resolver: AST → symbol → module in the pinned venv | resolve pass working |
| 6 | Introspection probe + subprocess JSON bridge. Handle the edge cases | probe working, failure rate measured |
| 7 | Diff engine + the six error classes | classifier working |
| 8 | Repair loop + verification | **A4 arm complete — first real number** |
| 9 | Full eval: all five arms, 3 seeds, error-class breakdown | main table |
| 10 | Ablations + private-library experiment | the memorable slide |
| 11 | Package it: CLI, `pip install`, optional editor wrapper. Record the demo | shipped tool |
| 12 | Slides, README with the headline table, repo release | done |

**Weeks 3–4 are the real gate.** If you can't reproduce a published number, every later
number is unmeasurable. Don't build past it.

**Slack:** there is none. If something slips, cut the editor wrapper (week 11) first, then
the ablations (week 10). Never cut weeks 3–4 or the private-library experiment.

---

## The three things that make it memorable

**1. The private-library demo.** Docs-RAG has nothing to retrieve; weight-editing has
nothing to train on. Introspection is unaffected. No competing method can make this claim,
and it's a structural argument — it holds even before you show numbers.

**2. Ship it.** `pip install pinpoint` on a slide reads completely differently from a
results table. A CLI is enough; an editor wrapper is better.

**3. Win on the error class nobody targets.** Signature and parameter changes — 26.6% of
execution failures, structurally unreachable by name substitution.

---

## Slide map

### Slide 1 — Introduction, Objectives, Contribution
LLMs write code against the library version in their training data; you're on a different
one. **Objective:** make generated code correct for the *installed* version. **Contribution:**
PinPoint — the first repair layer grounded in runtime introspection rather than
documentation.
*Open with the pandas `.append()` example. Everyone in the room has hit it.*

### Slide 2 — Background and Existing Work
The five papers in one table: retrieval, prompting, decoding-time substitution, weight
editing, execution feedback. **The limitation that unites them:** all are grounded in
documentation or static analysis; none inspects the installed package.
**The number that justifies the project: with complete correct docs, only 66.36% of
generated code executes.**

### Slide 3 — Proposed System and Architecture
The pipeline diagram from `02-system-design.md`. Input → generated code + pinned env.
Process → resolve, introspect, diff, repair, verify. Output → code that runs here.
Stack: Python, `ast`/`inspect`/`typing`, Docker, Ollama/OpenRouter.
*One line to land it: "we stopped giving the model documentation and started giving it the object."*

### Slide 4 — Results and Analysis
Main table (5 arms, visible/hidden/gap) + the error-class breakdown bar chart.
Call out two things: the signature-error column, and whether the visible/hidden gap
narrowed where self-debugging widened it.
*Screenshot: a caught-and-repaired case, before/after.*

### Slide 5 — Conclusion and Future Work
What was built, the headline delta, the private-library result.
Future: other languages, semantic behaviour changes with identical signatures (the hard
residue), IDE integration, introspection for agent tool surfaces generally.

---

## Demo script (90 seconds, rehearse it)

1. Ask the model for dataframe-dedup code. It writes `.append()`.
2. Run it. Fails on pandas 2.x — show the traceback.
3. Enable PinPoint. Same request.
4. Show the probe output: *not found · nearest: `concat` · removed in 2.0 · real signature*.
5. Repaired code. Runs.
6. Switch to the private SDK. Note there is no documentation anywhere. It still works.

Step 6 is the one they'll remember.
