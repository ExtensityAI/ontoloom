"""Foundation exceptions for the ontoloom core library.

Domain-specific errors live with the code that raises them; only the base class
and cross-cutting errors (raised from multiple modules) live here.
"""


class OntoloomError(Exception):
    """Base for all ontoloom domain errors."""


class StoreCorruptionError(OntoloomError):
    """Stored data failed deserialization. Indicates schema drift or corruption."""

    def __init__(self, detail: str, original: Exception):
        self.detail = detail
        self.original = original
        super().__init__(f"Corrupted stored data: {detail}")


class ConcurrentWriteError(OntoloomError):
    """Another writer held the SQLite write lock past the busy_timeout.

    The transaction has been rolled back. Safe to retry — persistent failures
    usually mean another process is holding a long write transaction open.
    """

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(f"Database is locked by another writer: {detail}. Retry the operation.")


class InternalError(OntoloomError):
    """Internal invariant violated. Indicates a bug in ontoloom itself, not user input."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class InvalidArgumentsError(OntoloomError):
    """Caller passed an invalid combination of arguments."""

    def __init__(self, message: str):
        super().__init__(message)
