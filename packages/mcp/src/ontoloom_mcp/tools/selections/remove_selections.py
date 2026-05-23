from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.selections.store import (
    remove_axiom_selections,
    remove_entity_selections,
)
from ontoloom.selections.types import AxiomSelectionName, EntitySelectionName
from ontoloom.utils import dquoted

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def remove_selections(
    path: OntologyPath,
    names: Annotated[tuple[AxiomSelectionName | EntitySelectionName, ...], MinLen(1)],
):
    """Remove selections by exact name. Best-effort -> reports any not found.

    Each entry in `names` is kind-prefixed (e.g. `"axioms:foo"` or
    `"entities:bar"`); the prefix selects the kind-table to remove from.
    Missing names are tolerated and listed in the result.

    To delete selections matching a glob, call `list_selections` first to
    discover the matching names, then pass them here.
    """
    axiom_refs = [n for n in names if isinstance(n, AxiomSelectionName)]
    entity_refs = [n for n in names if isinstance(n, EntitySelectionName)]

    ont = Ontology(path)
    with session(ont) as s:
        dropped_all = []
        not_found_all = []

        if axiom_refs:
            res_ax = remove_axiom_selections(s, axiom_refs)
            dropped_all.extend(res_ax.dropped)
            not_found_all.extend(res_ax.not_found)
        if entity_refs:
            res_ent = remove_entity_selections(s, entity_refs)
            dropped_all.extend(res_ent.dropped)
            not_found_all.extend(res_ent.not_found)
        s.commit()

        parts = []
        if dropped_all:
            items = ", ".join(f"{dquoted(d.name)} ({d.size})" for d in dropped_all)
            parts.append(f"Removed {len(dropped_all)} selections: {items}.")
        if not_found_all:
            parts.append(f"Not found: {', '.join(dquoted(n) for n in not_found_all)}.")
        return " ".join(parts) or "Nothing to remove."


tool_remove_selections = create_tool(
    remove_selections,
    name="remove_selections",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True),
)
