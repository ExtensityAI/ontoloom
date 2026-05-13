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
from ontoloom.utils import dquoted
from pydantic import ValidationError
from pydantic_core import ErrorDetails


def _format_one_error(err: ErrorDetails) -> str:
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
            return f"Ontology {dquoted(e.path)} not found. Use `create_ontology` to create it."
        case SelectionNotFoundError():
            return (
                f"Selection {dquoted(e.name)} does not exist. "
                f"Use `search_entities` or `match_axioms` (with `into=` set) to create one."
            )
        case StaleSelectionError():
            current = (
                f" Current: {e.name}@{e.current_hash} ({e.current_size} items)."
                if e.current_hash is not None and e.current_size is not None
                else " It no longer exists."
            )
            return f"Selection {dquoted(e.name)} has changed since you last observed it.{current}"
        case SelectionKindError():
            return (
                f"{dquoted(e.operation)} requires an {e.expected} selection, "
                f"but {dquoted(e.name)} is an {e.actual} selection."
            )
        case SelectionExprError():
            return f"Invalid set expression: {e}"
        case AxiomNotFoundError():
            return f"No axiom matching hash [{e.needle}]. Use `match_axioms` to find axiom hashes."
        case EntityNotFoundError():
            near = f" Similar entities: {', '.join(e.near_matches)}." if e.near_matches else ""
            return (
                f"Entity {dquoted(e.iri)} not found.{near} "
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
            return f"No prefix {dquoted(e.name)}. Use `set_prefix` to define it."
        case PrefixInUseError():
            return (
                f"Prefix {dquoted(e.name)} is still used by {e.count} entities. "
                f"Rename or remove those entities first, or use `rename_iri` to migrate them."
            )
        case UndeclaredPrefixError():
            return (
                f"Undeclared prefix(es): {', '.join(dquoted(p) for p in sorted(e.prefixes))}. "
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
                f"Closest variant: {dquoted(e.closest_variant)}.{missing}{unknown} "
                f"Check the schema for {dquoted(e.closest_variant)}, "
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
