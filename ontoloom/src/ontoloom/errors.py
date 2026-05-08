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


class UnionDispatchError(OntoloomError):
    """Input dict does not match any variant of a discriminated union.

    Carries the best-fit variant and the precise discrepancy so the consumer
    layer (MCP, REPL, etc.) can render a focused message instead of dumping
    every union member's signature.
    """

    def __init__(
        self,
        union_name: str,
        closest_variant: str,
        keys: frozenset[str],
        missing: frozenset[str],
        unknown: frozenset[str],
    ):
        self.union_name = union_name
        self.closest_variant = closest_variant
        self.keys = keys
        self.missing = missing
        self.unknown = unknown
        parts = [f"input does not match any {union_name} variant; closest: {closest_variant!r}"]
        if missing:
            parts.append(f"missing required field(s) {sorted(missing)}")
        if unknown:
            parts.append(f"unknown field(s) {sorted(unknown)}")
        super().__init__("; ".join(parts))
