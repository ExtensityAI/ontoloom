"""Domain error -> ToolError translation decorator for MCP tools."""

import functools
from collections.abc import Callable

from fastmcp.exceptions import ToolError
from ontoloom.axioms.store import AmbiguousHashError, AxiomNotFoundError
from ontoloom.connection import OntologyNotFoundError
from ontoloom.entities.store import EntityNotFoundError
from ontoloom.errors import (
    InternalError,
    OntoloomError,
    StoreCorruptionError,
    UnionDispatchError,
)
from ontoloom.prefixes import PrefixInUseError, PrefixNotFoundError
from ontoloom.selections.store import (
    SelectionExprError,
    SelectionKindError,
    SelectionNotFoundError,
    StaleSelectionError,
)
from pydantic import ValidationError


def _format_validation_error(e: ValidationError) -> str:
    errors = e.errors()
    if len(errors) == 1:
        err = errors[0]
        loc = ".".join(str(x) for x in err["loc"]) or "input"
        return f"Invalid input ({loc}): {err['msg']}"
    lines = [
        f"  - {'.'.join(str(x) for x in err['loc']) or 'input'}: {err['msg']}" for err in errors
    ]
    return "Invalid input:\n" + "\n".join(lines)


class MutuallyExclusiveError(ToolError):
    """Tool called with multiple parameters when only one was allowed."""

    def __init__(self, params: tuple[str, ...], hint: str = ""):
        self.params = params
        msg = f"Pass exactly one of {list(params)!r}, not multiple."
        if hint:
            msg += f" {hint}"
        super().__init__(msg)


class MissingRequiredError(ToolError):
    """Tool called without any of a set of mutually-required parameters."""

    def __init__(self, params: tuple[str, ...], hint: str = ""):
        self.params = params
        msg = f"Pass at least one of {list(params)!r}."
        if hint:
            msg += f" {hint}"
        super().__init__(msg)


# A: this hints dict is horrible, how about we do a match instead?
_HINTS: dict[type[Exception], Callable[..., str]] = {
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
    SelectionExprError: lambda e: f"Invalid set expression: {e}",
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
    PrefixInUseError: lambda e: (
        f"Prefix {e.name!r} is still used by {e.count} entities. "
        f"Rename or remove those entities first, or use `rename_iri` to migrate them."
    ),
    StoreCorruptionError: lambda e: (
        f"Data integrity error: {e.detail}. This may indicate database corruption."
    ),
    InternalError: lambda e: f"Internal error: {e.detail}. Please file a bug report.",
    UnionDispatchError: lambda e: (
        f"Input does not match any {e.union_name} variant. "
        f"Closest variant: {e.closest_variant!r}."
        + (f" Missing required field(s): {sorted(e.missing)}." if e.missing else "")
        + (f" Unknown field(s): {sorted(e.unknown)}." if e.unknown else "")
        + f" Check the schema for {e.closest_variant!r}, "
        f"or pick a different {e.union_name} variant."
    ),
    FileNotFoundError: lambda e: f"File or directory not found: {e}",
    PermissionError: lambda e: f"Access denied: {e}",
    ValidationError: _format_validation_error,
}

# Exception types we translate at MCP boundaries (decorator and middleware).
_TRANSLATABLE: tuple[type[Exception], ...] = (
    OntoloomError,
    FileNotFoundError,
    PermissionError,
    ValidationError,
)


def format_error(e: Exception) -> str:
    """Render a translatable exception as a user-facing message via the hint dict."""
    builder = _HINTS.get(type(e), str)
    return builder(e)


def translate_errors(fn):
    """Catch translatable exceptions -> ToolError with hints. Let ToolError pass through.

    Bare ValueError is intentionally not caught: it represents a programming
    bug in calling code and should reach LastResortMiddleware so it gets logged.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except _TRANSLATABLE as e:
            raise ToolError(format_error(e)) from None

    return wrapper
