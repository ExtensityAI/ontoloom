from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology
from ontoloom.selections.store import (
    remove_selections as core_remove_selections,
)
from ontoloom.selections.store import (
    remove_selections_by_pattern,
)
from ontoloom.transactions import session

from ontoloom_mcp.components.errors import MissingRequiredError, MutuallyExclusiveError
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName, SelectionPattern


def remove_selections(
    path: OntologyPath,
    names: list[SelectionName] | None = None,
    pattern: SelectionPattern | None = None,
):
    """Remove selections by exact name or glob pattern.

    Provide exactly one of:
    - `names`: List of exact selection names. Best-effort -> reports any not found.
    - `pattern`: Glob (`*` matches any sequence, `?` matches one character),
      e.g. `audit_*`. Removes every selection whose name matches.
    """
    if names is not None and pattern is not None:
        raise MutuallyExclusiveError(("names", "pattern"))
    if names is None and pattern is None:
        raise MissingRequiredError(("names", "pattern"))

    ont = Ontology(path)
    with session(ont) as s:
        if pattern is not None:
            dropped = remove_selections_by_pattern(s, pattern)
            s.commit()
            if not dropped:
                return f"No selections matched pattern {str(pattern)!r}."
            items = ", ".join(f"{str(d.name)!r} ({d.size})" for d in dropped)
            return f"Removed {len(dropped)} selections matching {str(pattern)!r}: {items}."

        result = core_remove_selections(s, names)  # pyright: ignore[reportArgumentType]
        s.commit()

    parts = []
    if result.dropped:
        items = ", ".join(f"{str(d.name)!r} ({d.size})" for d in result.dropped)
        parts.append(f"Removed {len(result.dropped)} selections: {items}.")
    if result.not_found:
        parts.append(f"Not found: {', '.join(repr(str(n)) for n in result.not_found)}.")
    return " ".join(parts) or "Nothing to remove."


tool_remove_selections = create_tool(
    remove_selections,
    name="remove_selections",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True),
)
