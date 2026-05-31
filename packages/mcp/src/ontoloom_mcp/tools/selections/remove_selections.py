from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.selections.store import remove_selections_any
from ontoloom.selections.types import SelectionName
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import format_kinded_count
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def remove_selections(
    path: OntologyPath,
    names: Annotated[tuple[SelectionName, ...], MinLen(1)],
):
    """Remove selections by exact name. Best-effort -> reports any not found.

    Each entry in `names` is a bare selection name (e.g. `"foo"`); the kind is
    resolved by lookup. Missing names are tolerated and listed in the result.

    To delete selections matching a glob, call `list_selections` first to
    discover the matching names, then pass them here.
    """
    ont = Ontology(path)
    with session(ont) as s:
        res = remove_selections_any(s, names)
        s.commit()

    parts = []
    if res.dropped:
        items = ", ".join(
            f"{dquoted(d.name)} ({format_kinded_count(d.kind, d.size)})" for d in res.dropped
        )
        noun = "selection" if len(res.dropped) == 1 else "selections"
        parts.append(f"Removed {len(res.dropped)} {noun}: {items}.")
    if res.not_found:
        parts.append(f"Not found: {', '.join(dquoted(n) for n in res.not_found)}.")
    return " ".join(parts)


tool_remove_selections = create_tool(
    remove_selections,
    name="remove_selections",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True),
)
