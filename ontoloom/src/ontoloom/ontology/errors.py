"""Domain exceptions for the ontoloom core library."""

from pathlib import Path


class OntoloomError(Exception):
    """Base for all ontoloom domain errors."""


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

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Selection {name!r} has changed since you last observed it.")


class SelectionKindError(OntoloomError):
    """Wrong selection kind for the requested operation."""

    def __init__(self, name: str, expected: str, actual: str, operation: str):
        self.name = name
        self.expected = expected
        self.actual = actual
        self.operation = operation
        super().__init__(
            f"'{operation}' requires a {expected} selection, but {name!r} is a {actual} selection."
        )


class AxiomNotFoundError(OntoloomError):
    """No axiom matches the given hash prefix."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        super().__init__(f"No axiom matching hash prefix [{prefix}].")


class AmbiguousHashError(OntoloomError):
    """Hash prefix matches multiple axioms."""

    def __init__(self, prefix: str, count: int, samples: list[str]):
        self.prefix = prefix
        self.count = count
        self.samples = samples
        max_shown = 10
        shown = ", ".join(samples[:max_shown])
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
