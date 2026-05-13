"""Domain error -> ToolError translation decorator for MCP tools."""

import functools

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
from ontoloom.prefixes import PrefixInUseError, PrefixNotFoundError, UndeclaredPrefixError
from ontoloom.selections.store import (
    SelectionExprError,
    SelectionKindError,
    SelectionNotFoundError,
    StaleSelectionError,
)
from pydantic import ValidationError
from pydantic_core import ErrorDetails

# Friendlier descriptions for the regex patterns we attach to Pydantic Field(pattern=...)
# definitions. When a `string_pattern_mismatch` error fires, we swap the bare
# "String should match pattern '...'" message for "<description>; must match
# '...'", so the LLM sees what the field is for. TypedStr-derived types raise
# clean errors via `parse()` and don't need an entry here.
_PATTERN_DESCRIPTIONS: dict[str, str] = {
    r"^$|^[a-zA-Z]{2,3}(-[a-zA-Z0-9]+)*$": "BCP 47 language tag (e.g. 'en', 'en-GB')",
}


def _format_one_error(err: ErrorDetails) -> str:
    if err["type"] == "string_pattern_mismatch":
        pattern = (err.get("ctx") or {}).get("pattern", "")
        if pattern in _PATTERN_DESCRIPTIONS:
            input_repr = repr(err.get("input"))
            return (
                f"{input_repr} is not a valid {_PATTERN_DESCRIPTIONS[pattern]}; "
                f"must match {pattern!r}"
            )
    return err["msg"]


def _format_validation_error(e: ValidationError) -> str:
    errors = e.errors()
    if len(errors) == 1:
        err = errors[0]
        loc = ".".join(str(x) for x in err["loc"]) or "input"
        return f"Invalid input ({loc}): {_format_one_error(err)}"
    lines = [
        f"  - {'.'.join(str(x) for x in err['loc']) or 'input'}: {_format_one_error(err)}"
        for err in errors
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


# Exception types we translate at MCP boundaries (decorator and middleware).
TRANSLATABLE: tuple[type[Exception], ...] = (
    OntoloomError,
    FileNotFoundError,
    PermissionError,
    ValidationError,
)


def format_error(e: Exception) -> str:  # noqa: C901
    """Render a translatable exception as a user-facing message."""
    match e:
        case OntologyNotFoundError():
            return f"Ontology '{e.path}' not found. Use `create_ontology` to create it."
        case SelectionNotFoundError():
            return (
                f"Selection {str(e.name)!r} does not exist. "
                f"Use `search_entities` or `match_axioms` (with `into=` set) to create one."
            )
        case StaleSelectionError():
            current = (
                f" Current: {e.name}@{e.current_hash} ({e.current_size} items)."
                if e.current_hash is not None and e.current_size is not None
                else " It no longer exists."
            )
            return f"Selection {str(e.name)!r} has changed since you last observed it.{current}"
        case SelectionKindError():
            return (
                f"`{e.operation}` requires an {e.expected} selection, "
                f"but {str(e.name)!r} is an {e.actual} selection."
            )
        case SelectionExprError():
            return f"Invalid set expression: {e}"
        case AxiomNotFoundError():
            return (
                f"No axiom matching hash prefix [{e.prefix}]. "
                f"Use `match_axioms` to find axiom hashes."
            )
        case EntityNotFoundError():
            near = f" Similar entities: {', '.join(e.near_matches)}." if e.near_matches else ""
            return (
                f"Entity {str(e.iri)!r} not found.{near} "
                f"Use `search_entities` to find entities by name."
            )
        case AmbiguousHashError():
            more = f", ... ({e.count - 10} more)" if e.count > 10 else ""
            return (
                f"[{e.prefix}] matches {e.count} axioms: "
                f"{', '.join(e.distinguishing_prefixes[:10])}{more}. "
                f"Each shown prefix is the shortest that uniquely identifies its axiom."
            )
        case PrefixNotFoundError():
            return f"No prefix {str(e.name)!r}. Use `set_prefix` to define it."
        case PrefixInUseError():
            return (
                f"Prefix {str(e.name)!r} is still used by {e.count} entities. "
                f"Rename or remove those entities first, or use `rename_iri` to migrate them."
            )
        case UndeclaredPrefixError():
            return (
                f"Undeclared prefix(es): {', '.join(repr(str(p)) for p in sorted(e.prefixes))}. "
                f"Use `set_prefix` to declare them, or use a built-in prefix "
                f"('rdf', 'rdfs', 'owl', 'xsd')."
            )
        case StoreCorruptionError():
            return f"Data integrity error: {e.detail}. This may indicate database corruption."
        case InternalError():
            return f"Internal error: {e.detail}. Please file a bug report."
        case UnionDispatchError():
            missing = f" Missing required field(s): {sorted(e.missing)}." if e.missing else ""
            unknown = f" Unknown field(s): {sorted(e.unknown)}." if e.unknown else ""
            return (
                f"Input does not match any {e.union_name} variant. "
                f"Closest variant: {e.closest_variant!r}.{missing}{unknown} "
                f"Check the schema for {e.closest_variant!r}, "
                f"or pick a different {e.union_name} variant."
            )
        case FileNotFoundError():
            return f"File or directory not found: {e}"
        case PermissionError():
            return f"Access denied: {e}"
        case ValidationError():
            return _format_validation_error(e)
        case _:
            return str(e)


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
        except TRANSLATABLE as e:
            raise ToolError(format_error(e)) from None

    return wrapper
