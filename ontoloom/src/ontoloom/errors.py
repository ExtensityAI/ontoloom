from ontoloom.utils import dquoted

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
        parts = [
            f"input does not match any {union_name} variant; closest: {dquoted(closest_variant)}"
        ]
        if missing:
            parts.append(f"missing required field(s) {sorted(missing)}")
        if unknown:
            parts.append(f"unknown field(s) {sorted(unknown)}")
        super().__init__("; ".join(parts))
