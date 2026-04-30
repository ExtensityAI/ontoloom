"""Domain exceptions for the ontoloom core library."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ontoloom.ontology.types import SelectionKind


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


class OntologyNotFoundError(OntoloomError, FileNotFoundError):
    """Ontology database file does not exist."""

    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"'{path}' does not exist.")


class OntologyExistsError(OntoloomError, FileExistsError):
    """Ontology database file already exists."""

    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"'{path}' already exists.")


class SelectionNotFoundError(OntoloomError):
    """Named selection does not exist."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Selection {name!r} does not exist.")


class StaleSelectionError(OntoloomError):
    """Selection has changed since last observed."""

    def __init__(self, name: str, supplied_prefix: str, current_hash: str | None):
        self.name = name
        self.supplied_prefix = supplied_prefix
        self.current_hash = current_hash
        current = current_hash[:12] if current_hash else "<absent>"
        super().__init__(
            f"Selection {name!r} has changed (your prefix: {supplied_prefix!r}, "
            f"current hash: {current!r}). Re-read the selection to get the current hash."
        )


class SelectionKindError(OntoloomError):
    """Wrong selection kind for the requested operation."""

    def __init__(self, name: str, expected: SelectionKind, actual: SelectionKind, operation: str):
        self.name = name
        self.expected = expected
        self.actual = actual
        self.operation = operation
        super().__init__(
            f"'{operation}' requires an {expected} selection, but {name!r} is an {actual} selection."
        )


class AxiomNotFoundError(OntoloomError):
    """No axiom matches the given hash prefix."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        super().__init__(f"No axiom matching hash prefix [{prefix}].")


class EntityNotFoundError(OntoloomError):
    """No entity with the given IRI exists in the ontology.

    `near_matches` are IRIs of entities with similar local names — populated by
    `entities.get` so callers can show "did you mean…?" without re-querying.
    """

    def __init__(self, iri: str, near_matches: list[str] | None = None):
        self.iri = iri
        self.near_matches = near_matches or []
        super().__init__(f"Entity {iri!r} not found.")


class AmbiguousHashError(OntoloomError):
    """Hash prefix matches multiple axioms.

    `distinguishing_prefixes` are the minimum-length prefixes that uniquely
    identify each match — the caller can copy any of them verbatim to retry.
    """

    def __init__(self, prefix: str, count: int, distinguishing_prefixes: list[str]):
        self.prefix = prefix
        self.count = count
        self.distinguishing_prefixes = distinguishing_prefixes
        max_shown = 10
        shown = ", ".join(distinguishing_prefixes[:max_shown])
        suffix = f", ... ({count - max_shown} more)" if count > max_shown else ""
        super().__init__(f"[{prefix}] matches {count} axioms: {shown}{suffix}.")


class InvalidHashError(OntoloomError):
    """Hash prefix contains non-hex characters."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        super().__init__(f"[{prefix}] is not a valid hex hash prefix.")


class PrefixNotFoundError(OntoloomError):
    """IRI prefix mapping does not exist."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"No prefix {name!r}.")


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


class OntologySchemaError(OntoloomError):
    """Database is not an ontoloom store or its schema version does not match."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)
