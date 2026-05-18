from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.selections.store import remove_selections as core_remove_selections
from ontoloom.selections.types import SelectionRef
from ontoloom.utils import dquoted

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def remove_selections(
    path: OntologyPath,
    names: Annotated[tuple[SelectionRef, ...], MinLen(1)],
):
    """Remove selections by exact name. Best-effort -> reports any not found.

    Each entry in `names` is kind-prefixed (e.g. `"axioms:foo"` or
    `"entities:bar"`); removal is by bare name only -- the kind prefix is
    informational and not verified against the stored selection.

    To delete selections matching a glob, call `list_selections` first to
    discover the matching names, then pass them here.
    """
    bare_names = [ref.bare for ref in names]
    ont = Ontology(path)
    with session(ont) as s:
        result = core_remove_selections(s, bare_names)
        s.commit()
        parts = []
        if result.dropped:
            items = ", ".join(f"{dquoted(d.name)} ({d.size})" for d in result.dropped)
            parts.append(f"Removed {len(result.dropped)} selections: {items}.")
        if result.not_found:
            parts.append(f"Not found: {', '.join(dquoted(n) for n in result.not_found)}.")
        return " ".join(parts) or "Nothing to remove."


tool_remove_selections = create_tool(
    remove_selections,
    name="remove_selections",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True),
)
