class HalyardError(Exception):
    """Base class for all halyard errors."""


class UnknownQueue(HalyardError):
    """Raised when a queue was never written to."""


class QuotaExceeded(HalyardError):
    """Raised when a queue already holds `Client.max_ready` ready jobs."""
