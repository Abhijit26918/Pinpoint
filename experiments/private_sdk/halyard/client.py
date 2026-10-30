from .errors import QuotaExceeded, UnknownQueue
from .models import Job, Priority


class Client:
    """In-memory job queue with a logical clock (nothing here sleeps or reads wall time)."""

    max_ready = 1000

    def __init__(self, namespace: str = "default", *, max_attempts: int = 3):
        self.namespace = namespace
        self.max_attempts = max_attempts
        self.now = 0.0
        self._jobs: dict[str, list[Job]] = {}
        self._next_id = 1

    # ---- clock
    def advance_clock(self, seconds: float) -> None:
        """Move the logical clock forward; leases that expire return their jobs to the ready state."""
        self.now += seconds
        for jobs in self._jobs.values():
            for j in jobs:
                if j.state == "leased" and j.lease_expires <= self.now:
                    j.state, j.lease_expires = "ready", None

    # ---- producing
    def enqueue(self, queue: str, payload, *, delay: float = 0.0, priority: Priority = Priority.NORMAL,
                dedupe_key: str | None = None) -> Job:
        """Add a job. A second enqueue with the same dedupe_key on the same queue returns the first job."""
        jobs = self._jobs.setdefault(queue, [])
        if dedupe_key is not None:
            for j in jobs:
                if j.dedupe_key == dedupe_key and j.state != "done":
                    return j
        if sum(j.state == "ready" for j in jobs) >= self.max_ready:
            raise QuotaExceeded(queue)
        job = Job(self._next_id, queue, payload, priority, dedupe_key=dedupe_key, ready_at=self.now + delay,
                  _client=self)
        self._next_id += 1
        jobs.append(job)
        return job

    # ---- consuming
    def lease(self, queue: str, *, max_jobs: int = 1, visibility_timeout: float = 30.0) -> list[Job]:
        """Lease up to max_jobs ready jobs, highest priority first, then oldest. Returns [] when none are ready."""
        jobs = self._get(queue)
        ready = [j for j in jobs if j.state == "ready" and j.ready_at <= self.now]
        ready.sort(key=lambda j: (-int(j.priority), j.id))
        leased = ready[:max_jobs]
        for j in leased:
            j.state, j.attempts = "leased", j.attempts + 1
            j.lease_expires = self.now + visibility_timeout
        return leased

    def ack(self, job: Job, *, result=None) -> None:
        """Mark a leased job as done and store its result."""
        job.state, job.result, job.lease_expires = "done", result, None

    def nack(self, job: Job, *, requeue_after: float = 0.0, reason: str | None = None) -> None:
        """Give a leased job back. After max_attempts attempts it becomes dead instead of ready."""
        job.lease_expires = None
        if job.attempts >= self.max_attempts:
            job.state, job.result = "dead", reason
        else:
            job.state, job.ready_at = "ready", self.now + requeue_after

    def _extend(self, job: Job, seconds: float) -> None:
        job.lease_expires += seconds

    # ---- inspecting
    def stats(self, queue: str) -> dict:
        """Counts of jobs per state: {'ready': n, 'leased': n, 'done': n, 'dead': n}."""
        counts = {"ready": 0, "leased": 0, "done": 0, "dead": 0}
        for j in self._get(queue):
            counts[j.state] += 1
        return counts

    def peek(self, queue: str, *, limit: int = 10) -> list[Job]:
        """Ready jobs in lease order, without leasing them."""
        ready = [j for j in self._get(queue) if j.state == "ready" and j.ready_at <= self.now]
        ready.sort(key=lambda j: (-int(j.priority), j.id))
        return ready[:limit]

    def purge(self, queue: str, *, include_dead: bool = False) -> int:
        """Delete ready jobs (and dead ones if include_dead). Returns how many were deleted."""
        jobs = self._get(queue)
        keep = [j for j in jobs if not (j.state == "ready" or (include_dead and j.state == "dead"))]
        removed = len(jobs) - len(keep)
        self._jobs[queue] = keep
        return removed

    def queues(self) -> list[str]:
        """Names of all queues that have been written to, sorted."""
        return sorted(self._jobs)

    def _get(self, queue: str) -> list[Job]:
        if queue not in self._jobs:
            raise UnknownQueue(queue)
        return self._jobs[queue]
