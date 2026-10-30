# harness

Week 2. GitChameleon 2.0 runner: SQLite cache keyed by
`(model, model_version, problem_id, config, seed)`, retry with backoff, resumable state,
per-problem timeout, JSONL attempt log, provider swap by config. See
`docs/02-system-design.md` §6–7.
