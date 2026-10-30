# PinPoint — Project Brief

**Owner:** Prabhas · **Window:** 12 weeks · **Budget:** ~$10, no GPU
**Primary output:** working system + 5-slide presentation. Paper optional.

---

## 1. The problem

An LLM's knowledge of a library is frozen at its training cutoff. The library isn't.
pandas removed `.append()` in 2.0, sklearn dropped `normalize=`, numpy renamed things.
The model writes confident code against a version you don't have.

Published numbers on how bad it is:
- Deprecated API usage rate runs **25–38%** across models, and rises to **70–90%** when
  the surrounding prompt context is itself outdated. Larger models are *worse*.
- Even when handed the **complete, correct documentation** for the changed API, adoption
  reaches 92.87% but the **executable rate is only 66.36%**. The authors' conclusion:
  documentation is necessary but not sufficient.
- Of the execution failures, **26.6% are wrong parameters** — the largest category of
  update-related failure. (Precisely: 26.6% of 781 failures under the best prompt; 47.9% of
  failures were not update-related at all. Models were mostly small open ones. See
  docs/01-related-work.md.)

## 2. Why existing fixes fall short

Every current approach hands the model **documentation** in some form:

| Approach | Example | Limit |
|---|---|---|
| Version-aware RAG | LibEvolutionEval | needs scraped docs; retrieval quality varies by version |
| Prompt injection | INSERTPROMPT | fix rate as low as 25.7% on smaller models |
| Decoding-time replacement | REPLACEAPI | **name substitution only** — cannot fix a signature change |
| Weight editing | AdaLoRA-L + 10 others | one edit per API; no signature-change evaluation |
| Execution feedback | GitChameleon self-debug | works (30%→52.1%), but visible/hidden gap *widens* — fixes the test, not the contract |

**The gap, confirmed across all five papers: not one of them introspects the installed
package at runtime.** They use `requirements.txt`, dependency matrices, scraped docs,
changelogs, and ASTs. Never the live object.

## 3. The thesis

> Documentation describes what a library *was said to do*. Introspection reports what the
> installed object *actually accepts, right now*. Use the second.

`inspect.signature()`, `typing.get_type_hints()`, `inspect.getmembers()` and captured
`DeprecationWarning`s are free, exact, and cannot disagree with the installed version.

## 4. Contributions claimed

1. **Introspection as a repair oracle** — the first version-correctness layer grounded in
   runtime object inspection rather than documentation.
2. **Targeting the signature/parameter error class** that name-replacement methods
   structurally cannot fix.
3. **A private-library result** — introspection works on code no model has seen and no
   documentation covers. Docs-RAG and weight-editing cannot.
4. A shipped tool (`pip install` / editor wrapper), not just a results table.

## 5. Scope guard

**In:** Python. Signature, deprecation, and moved-symbol errors. GitChameleon 2.0 as the
evaluation set. One or two models with published baselines.

**Out:** building a new benchmark (four already exist). Any weight training. Other
languages. Semantic behaviour changes with identical signatures — note as future work.

## 6. Kill criteria

Stop or rethink if:
- **Weeks 1–2:** you cannot reproduce a published baseline number within a few points.
  Everything downstream is unmeasurable until this works.
- **Week 1:** a paper already does runtime introspection for repair. Check first.
- **Week 6:** introspection gives under ~3 points over plain self-debugging across the
  board *and* no advantage on the signature-error class. Then the thesis is wrong — say
  so, and pivot the project to the private-library case, which still stands alone.
