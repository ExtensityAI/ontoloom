from mcp.types import ToolAnnotations
from ontoloom.ontology import selections
from ontoloom.ontology.connection import Ontology

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName, SelectionPattern


def rm_selections(
    path: OntologyPath,
    names: list[SelectionName] | None = None,
    pattern: SelectionPattern | None = None,
):
    """Remove selections by exact name or glob pattern.

    Provide exactly one of:
    - `names`: List of exact selection names. Best-effort — reports any not found.
    - `pattern`: Glob (`*` matches any sequence, `?` matches one character),
      e.g. `audit_*`. Removes every selection whose name matches.
    """
    if (names is None) == (pattern is None):
        msg = "Provide exactly one of 'names' or 'pattern'."
        raise ValueError(msg)

    with Ontology(path) as ont:
        if pattern is not None:
            dropped = selections.remove_by_pattern(ont, pattern)
            if not dropped:
                return f"No selections matched pattern {pattern!r}."
            items = ", ".join(f"{name!r} ({count})" for name, count in dropped)
            return f"Removed {len(dropped)} selections matching {pattern!r}: {items}."

        dropped_names, not_found = selections.remove(ont, names)  # pyright: ignore[reportArgumentType]

    parts = []
    if dropped_names:
        items = ", ".join(f"{name!r} ({count})" for name, count in dropped_names)
        parts.append(f"Removed {len(dropped_names)} selections: {items}.")
    if not_found:
        parts.append(f"Not found: {', '.join(repr(n) for n in not_found)}.")
    return " ".join(parts) or "Nothing to remove."


tool_rm_selections = create_tool(
    rm_selections,
    name="rm_selections",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True),
)
