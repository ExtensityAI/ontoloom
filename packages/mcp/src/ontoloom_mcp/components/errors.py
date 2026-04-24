"""Domain error → ToolError translation decorator for MCP tools."""

import functools
from collections.abc import Callable

from fastmcp.exceptions import ToolError
from ontoloom.ontology.errors import (
    AmbiguousHashError,
    AxiomNotFoundError,
    InvalidHashError,
    OntologyExistsError,
    OntologyNotFoundError,
    OntoloomError,
    PrefixNotFoundError,
    SelectionKindError,
    SelectionNotFoundError,
    StaleSelectionError,
    StoreCorruptionError,
)

_HINTS: dict[type[OntoloomError], Callable[..., str]] = {
    OntologyNotFoundError: lambda e: (
        f"Ontology '{e.path}' not found. Use create_ontology to create it."
    ),
    OntologyExistsError: lambda e: str(e),
    SelectionNotFoundError: lambda e: (
        f"Selection {e.name!r} does not exist. "
        f"Use search_entities(select=...) or search_axioms(select=...) to create one."
    ),
    StaleSelectionError: lambda e: (
        f"Selection {e.name!r} has changed since you last observed it. "
        f"Use read_selection or list_selections to get the current sel@ hash."
    ),
    SelectionKindError: lambda e: (
        f"'{e.operation}' requires a {e.expected} selection, "
        f"but {e.name!r} is a {e.actual} selection."
    ),
    AxiomNotFoundError: lambda e: (
        f"No axiom matching hash prefix [{e.prefix}]. Use search_axioms to find axiom hashes."
    ),
    AmbiguousHashError: lambda e: (
        f"[{e.prefix}] matches {e.count} axioms: "
        f"{', '.join(e.samples[:10])}"
        f"{f', ... ({e.count - 10} more)' if e.count > 10 else ''}. "
        f"Use a longer prefix."
    ),
    InvalidHashError: lambda e: str(e),
    PrefixNotFoundError: lambda e: f"No prefix {e.name!r}. Use set_prefix to define it.",
    StoreCorruptionError: lambda e: (
        f"Data integrity error: {e.detail}. This may indicate database corruption."
    ),
}


def translate_errors(fn):
    """Catch OntoloomError → ToolError with hints. Let ToolError pass through."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except OntoloomError as e:
            builder = _HINTS.get(type(e), str)
            raise ToolError(builder(e)) from e
        except ValueError as e:
            raise ToolError(str(e)) from e

    return wrapper
