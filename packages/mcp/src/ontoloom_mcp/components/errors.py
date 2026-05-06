"""Domain error -> ToolError translation decorator for MCP tools."""

import functools
from collections.abc import Callable

from fastmcp.exceptions import ToolError
from ontoloom.axioms.store import AmbiguousHashError, AxiomNotFoundError
from ontoloom.connection import OntologyNotFoundError
from ontoloom.entities.store import EntityNotFoundError
from ontoloom.errors import (
    BadRequestError,
    InternalError,
    OntoloomError,
    StoreCorruptionError,
)
from ontoloom.prefixes import PrefixNotFoundError
from ontoloom.selections.store import (
    SelectionKindError,
    SelectionNotFoundError,
    StaleSelectionError,
)

# A: this hints dict is horrible, how about we do a match instead?
_HINTS: dict[type[OntoloomError], Callable[..., str]] = {
    OntologyNotFoundError: lambda e: (
        f"Ontology '{e.path}' not found. Use `create_ontology` to create it."
    ),
    SelectionNotFoundError: lambda e: (
        f"Selection {str(e.name)!r} does not exist. "
        f"Use `search_entities` or `match_axioms` (with `into=` set) to create one."
    ),
    StaleSelectionError: lambda e: (
        f"Selection {str(e.name)!r} has changed since you last observed it. "
        f"Use `read_selection` or `list_selections` to get the current hash."
    ),
    SelectionKindError: lambda e: (
        f"`{e.operation}` requires an {e.expected} selection, "
        f"but {str(e.name)!r} is an {e.actual} selection."
    ),
    AxiomNotFoundError: lambda e: (
        f"No axiom matching hash prefix [{e.prefix}]. Use `match_axioms` to find axiom hashes."
    ),
    EntityNotFoundError: lambda e: (
        f"Entity {str(e.iri)!r} not found."
        + (f" Similar entities: {', '.join(e.near_matches)}." if e.near_matches else "")
        + " Use `search_entities` to find entities by name."
    ),
    AmbiguousHashError: lambda e: (
        f"[{e.prefix}] matches {e.count} axioms: "
        f"{', '.join(e.distinguishing_prefixes[:10])}"
        f"{f', ... ({e.count - 10} more)' if e.count > 10 else ''}. "
        f"Each shown prefix is the shortest that uniquely identifies its axiom."
    ),
    PrefixNotFoundError: lambda e: f"No prefix {str(e.name)!r}. Use `set_prefix` to define it.",
    StoreCorruptionError: lambda e: (
        f"Data integrity error: {e.detail}. This may indicate database corruption."
    ),
    BadRequestError: lambda e: e.message,
    InternalError: lambda e: f"Internal error: {e.detail}. Please file a bug report.",
}


def translate_errors(fn):
    """Catch OntoloomError -> ToolError with hints. Let ToolError pass through.

    Bare ValueError is intentionally not caught: user-input precondition failures
    raise BadRequestError; any remaining ValueError represents a programming bug
    and should reach LastResortMiddleware so it gets logged.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except OntoloomError as e:
            builder = _HINTS.get(type(e), str)
            raise ToolError(builder(e)) from None

    return wrapper
