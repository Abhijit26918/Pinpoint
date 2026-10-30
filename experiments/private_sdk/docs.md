# halyard 2.3.0 - API reference

`import halyard`. An in-memory job queue with a logical clock (`Client.now`); nothing sleeps.

## halyard.Client(namespace="default", *, max_attempts=3)
Attribute `max_ready` (default 1000): a queue refuses new ready jobs beyond this (raises `QuotaExceeded`).

- `enqueue(queue, payload, *, delay=0.0, priority=Priority.NORMAL, dedupe_key=None) -> Job`
  Add a job. With `dedupe_key`, a second enqueue with the same key on the same queue returns the first job
  (unless that job is already done). `delay` hides the job until the clock has advanced that many seconds.
- `lease(queue, *, max_jobs=1, visibility_timeout=30.0) -> list[Job]`
  Take up to `max_jobs` ready jobs, highest priority first, then oldest. Returns `[]` if none are ready.
  Raises `UnknownQueue` if the queue never received a job.
- `ack(job, *, result=None)` - mark a leased job done and store `result`.
- `nack(job, *, requeue_after=0.0, reason=None)` - give a leased job back; it is ready again after
  `requeue_after` seconds. Once `job.attempts >= max_attempts` the job becomes `dead` instead.
- `stats(queue) -> dict` - `{'ready': n, 'leased': n, 'done': n, 'dead': n}`. Raises `UnknownQueue`.
- `peek(queue, *, limit=10) -> list[Job]` - ready jobs in lease order, without leasing them.
- `purge(queue, *, include_dead=False) -> int` - delete ready jobs (and dead ones with `include_dead`).
- `queues() -> list[str]` - sorted names of all queues that received a job.
- `advance_clock(seconds)` - move the logical clock; expired leases make their jobs ready again.

## halyard.Job
Fields: `id`, `queue`, `payload`, `priority`, `attempts`, `dedupe_key`, `state` (`ready|leased|done|dead`), `result`.
- `extend_lease(seconds)` - push the lease expiry further out.

## halyard.Priority
`LOW = 0`, `NORMAL = 5`, `URGENT = 9`.

## Errors
`HalyardError` (base), `UnknownQueue`, `QuotaExceeded`.

## Helpers
- `halyard.parse_duration(text) -> float` - `'1h30m'` -> `5400.0`; units d, h, m, s; a bare number is seconds.
- `halyard.batched(iterable, size)` - yields lists of at most `size` items.
