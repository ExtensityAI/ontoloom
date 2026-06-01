"""Foundation exceptions for the ontoloom core library.

Domain-specific errors live with the code that raises them; only the base class
and cross-cutting errors (raised from multiple modules) live here.
"""

from ontoloom.utils import dquoted


class OntoloomError(Exception):
    """Base for all ontoloom domain errors."""


class StoreCorruptionError(OntoloomError):
    """Stored data failed deserialization. Indicates schema drift or corruption."""

    def __init__(self, detail: str, original: Exception):
        self.detail = detail
        self.original = original
        super().__init__(f"Corrupted stored data: {detail}")


class InternalError(OntoloomError):
    """Internal invariant violated. Indicates a bug in ontoloom itself, not user input."""

    def __init__(self):
        super().__init__("internal invariant violated")


class DatabaseOpenError(OntoloomError):
    """Failed to open or read the underlying SQLite database file."""

    def __init__(self, path: str, detail: str):
        self.path = path
        self.detail = detail
        super().__init__(f"Cannot open ontology at {dquoted(path)}: {detail}")
