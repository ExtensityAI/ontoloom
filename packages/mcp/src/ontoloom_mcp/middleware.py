"""Custom middleware for the ontoloom MCP server."""

import logging
import time
from typing import override

import mcp.types as mt
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult
from ontoloom.axioms.hashing import AmbiguousHashError, AxiomNotFoundError
from ontoloom.connection import (
    OntologyExistsError,
    OntologyNotFoundError,
    OntologySchemaError,
)
from ontoloom.entities.reader import EntityNotFoundError
from ontoloom.errors import (
    DatabaseOpenError,
    InternalError,
    OntoloomError,
    StoreCorruptionError,
)
from ontoloom.models import UnionDispatchError
from ontoloom.prefixes.types import PrefixInUseError, PrefixNotFoundError, UndeclaredPrefixError
from ontoloom.selections.types import (
    SelectionExistsError,
    SelectionExprError,
    SelectionKindConflictError,
    SelectionKindMismatchError,
    SelectionNotFoundError,
)
from ontoloom.utils import dquoted
from pydantic import ValidationError

logger = logging.getLogger("ontoloom")


class TimingMiddleware(Middleware):
    """Log wall-clock time per tool call."""

    @override
    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        start = time.perf_counter()
        try:
            return await call_next(context)
        finally:
            elapsed = time.perf_counter() - start
            logger.info("tool %s completed in %.3fs", context.message.name, elapsed)


class ErrorMiddleware(Middleware):
    """Translate domain errors into agent-facing `ToolError` messages.

    Each `except` arm composes the MCP-enriched message inline (with
    tool-name hints where they help) and reraises `ToolError(...) from e`.
    Core types stay pure: their `__init__` carries the domain message only,
    no MCP knowledge. `ConfirmationRequiredError` is a `ToolError` subclass
    and passes through untouched via the first arm.
    """

    @override
    async def on_call_tool(  # noqa: C901
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        try:
            return await call_next(context)
        except ToolError:
            raise  # already translated; also covers ConfirmationRequiredError
        except EntityNotFoundError as e:
            logger.debug("translated", exc_info=e)
            near = f" Similar entities: {', '.join(e.near_matches)}." if e.near_matches else ""
            msg = (
                f"Entity {dquoted(e.iri)} not found.{near} "
                f"Use `find_entities` to find entities by name."
            )
            raise ToolError(msg) from e
        except AxiomNotFoundError as e:
            logger.debug("translated", exc_info=e)
            msg = f"No axiom matching hash [{e.needle}]. Use `match_axioms` to find axiom hashes."
            raise ToolError(msg) from e
        except AmbiguousHashError as e:
            logger.debug("translated", exc_info=e)
            shown = "\n".join(f"  [{p}] {ha.axiom}" for p, ha in e.matches[:10])
            more = f"\n  ... and {len(e.matches) - 10} more." if len(e.matches) > 10 else ""
            msg = (
                f"[{e.prefix}] matches {e.count} axioms:\n{shown}{more}\n"
                f"Each shown prefix is the shortest that uniquely identifies its axiom."
            )
            raise ToolError(msg) from e
        except PrefixNotFoundError as e:
            logger.debug("translated", exc_info=e)
            msg = f"No prefix {dquoted(e.name)}. Use `set_prefix` to define it."
            raise ToolError(msg) from e
        except PrefixInUseError as e:
            logger.debug("translated", exc_info=e)
            msg = (
                f"Prefix {dquoted(e.name)} is still used by {e.count} entities. "
                f"Rename or remove those entities first, or use `rename_iri` to migrate them."
            )
            raise ToolError(msg) from e
        except UndeclaredPrefixError as e:
            logger.debug("translated", exc_info=e)
            names = ", ".join(dquoted(p) for p in sorted(e.prefixes))
            msg = (
                f"Undeclared prefix(es): {names}. "
                f"Use `set_prefix` to declare them, or use a built-in prefix "
                f"('rdf', 'rdfs', 'owl', 'xsd')."
            )
            raise ToolError(msg) from e
        except SelectionNotFoundError as e:
            logger.debug("translated", exc_info=e)
            msg = (
                f"Selection {dquoted(e.name)} does not exist. "
                f"Use `find_entities` or `match_axioms` (with `into=` set) to create one."
            )
            raise ToolError(msg) from e
        except SelectionExistsError as e:
            logger.debug("translated", exc_info=e)
            msg = (
                f"Selection {dquoted(e.name)} already exists ({e.existing_size} items). "
                f'Pass mode="replace" to overwrite it.'
            )
            raise ToolError(msg) from e
        except SelectionKindConflictError as e:
            logger.debug("translated", exc_info=e)
            msg = (
                f"Selection {dquoted(e.name)} already exists as the other kind "
                f"(axiom vs entity); names are unique across both kinds. "
                f"Remove it first to reuse the name."
            )
            raise ToolError(msg) from e
        except SelectionKindMismatchError as e:
            logger.debug("translated", exc_info=e)
            msg = (
                f"Selection {dquoted(e.name)} contains {e.actual.value}, but this "
                f"operation requires {e.expected.value}. Pass a {e.expected.value} "
                f"selection, or use `create_selection` with `axioms_for=` / "
                f"`entities_in=` to convert."
            )
            raise ToolError(msg) from e
        except SelectionExprError as e:
            logger.debug("translated", exc_info=e)
            msg = f"Invalid set expression: {e}"
            raise ToolError(msg) from e
        except UnionDispatchError as e:
            logger.debug("translated", exc_info=e)
            missing = f" Missing required field(s): {sorted(e.missing)}." if e.missing else ""
            unknown = f" Unknown field(s): {sorted(e.unknown)}." if e.unknown else ""
            msg = (
                f"Input does not match any {e.union_name} variant. "
                f"Closest variant: {dquoted(e.closest_variant)}.{missing}{unknown} "
                f"Check the schema for {dquoted(e.closest_variant)}, "
                f"or pick a different {e.union_name} variant."
            )
            raise ToolError(msg) from e
        except OntologyNotFoundError as e:
            logger.debug("translated", exc_info=e)
            msg = f"Ontology {dquoted(e.path)} not found. Use `create_ontology` to create it."
            raise ToolError(msg) from e
        except OntologyExistsError as e:
            logger.debug("translated", exc_info=e)
            raise ToolError(str(e)) from e
        except OntologySchemaError as e:
            logger.debug("translated", exc_info=e)
            msg = f"Schema error: {e.detail}. The database may be from an incompatible version."
            raise ToolError(msg) from e
        except DatabaseOpenError as e:
            logger.debug("translated", exc_info=e)
            msg = f"Cannot open ontology at {dquoted(e.path)}: {e.detail}"
            raise ToolError(msg) from e
        except StoreCorruptionError as e:
            logger.exception("data corruption in tool %s", context.message.name)
            msg = f"Data integrity error: {e.detail}. This may indicate database corruption."
            raise ToolError(msg) from e
        except InternalError as e:
            logger.exception("internal invariant violated in tool %s", context.message.name)
            msg = "Internal error. Please file a bug."
            raise ToolError(msg) from e
        except ValidationError as e:
            logger.debug("translated", exc_info=e)
            raise ToolError(_render_pydantic(e)) from e
        except (FileNotFoundError, FileExistsError, PermissionError) as e:
            logger.debug("translated", exc_info=e)
            raise ToolError(str(e)) from e
        except OntoloomError as e:
            # Safety net for future subclasses without an explicit arm.
            logger.exception("unhandled OntoloomError subclass in tool %s", context.message.name)
            raise ToolError(str(e)) from e
        except Exception as e:
            logger.exception("unhandled exception in tool %s", context.message.name)
            msg = f"Internal error: {type(e).__name__}: {e}"
            raise ToolError(msg) from e


def _render_pydantic(e: ValidationError) -> str:
    errs = e.errors()
    if len(errs) == 1:
        loc = ".".join(str(x) for x in errs[0]["loc"]) or "input"
        return f"Invalid input ({loc}): {errs[0]['msg']}"
    lines = [f"  - {'.'.join(str(x) for x in err['loc']) or 'input'}: {err['msg']}" for err in errs]
    return "Invalid input:\n" + "\n".join(lines)
