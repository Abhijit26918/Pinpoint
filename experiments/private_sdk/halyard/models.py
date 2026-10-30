import enum
from dataclasses import dataclass, field


class Priority(enum.IntEnum):
    LOW = 0
    NORMAL = 5
    URGENT = 9


@dataclass
class Job:
    id: int
    queue: str
    payload: object
    priority: Priority = Priority.NORMAL
    attempts: int = 0
    dedupe_key: str | None = None
    ready_at: float = 0.0
    lease_expires: float | None = None
    state: str = "ready"            # ready | leased | done | dead
    result: object = None
    _client: object = field(default=None, repr=False, compare=False)

    def extend_lease(self, seconds: float) -> None:
        """Push this job's lease expiry `seconds` further into the future."""
        self._client._extend(self, seconds)
