"""Foundation exceptions for the ontoloom core library.

Domain-specific errors live with the code that raises them; only the base class
and cross-cutting errors (raised from multiple modules) live here.
"""


class OntoloomError(Exception):
    """Base for all ontoloom domain errors."""


class BadRequestError(OntoloomError):
    """User-input precondition failed at a core API boundary.

    Raise at user-facing entry points when arguments are individually well-typed
    but the combination violates a precondition (e.g. mismatched selection
    kinds, non-positive limits, prefix still in use). Use ValueError for
    programming errors that signal a bug in calling code.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class StoreCorruptionError(OntoloomError):
    """Stored data failed deserialization. Indicates schema drift or corruption."""

    def __init__(self, detail: str, original: Exception):
        self.detail = detail
        self.original = original
        super().__init__(f"Corrupted stored data: {detail}")


class InternalError(OntoloomError):
    """Internal invariant violated. Indicates a bug in ontoloom itself, not user input."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)
