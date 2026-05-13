from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.hashing import short_hash
from ontoloom.selections.store import read_selection as core_read_selection
from ontoloom.selections.types import (
    AxiomSelectionPage,
    EntitySelectionPage,
    SelectionName,
    ShowFilter,
)
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import format_axiom_annotations
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import Limit, Offset, OntologyPath


def read_selection(
    path: OntologyPath,
    name: SelectionName,
    limit: Limit = 20,
    offset: Offset = 0,
    show: ShowFilter = ShowFilter.ALL,
):
    """Paginated view of a selection's contents with missing-item visibility.

    - `show`: "all" (default), "present" (only items still in ontology),
      "missing" (only items removed since the selection was created).
      Use "missing" to audit a selection after ontology modifications.

    Always includes summary stats (total, present, missing) regardless of filter.
    Pagination applies after the show filter. For bulk verification, dispatch a
    subagent to paginate rather than reading everything into your context.
    """
    ont = Ontology(path)
    with session(ont) as s:
        page = core_read_selection(s, name, limit=limit, offset=offset, show=show)
        s.commit()

    meta = page.meta
    header = (
        f"Selection {dquoted(meta.locked)} ({meta.kind}): "
        f"{meta.size} total ({page.present} present, {page.missing} missing)"
    )

    end = offset + len(page.items)
    if not page.items:
        showing = f"0 results (filter: {show})."
    else:
        showing = f"Showing {offset + 1}-{end} of {page.total_filtered} (filter: {show}):"

    lines = [header, showing, ""]

    match page:
        case AxiomSelectionPage():
            for item in page.items:
                h = short_hash(item.hash)
                if item.axiom is None:
                    lines.append(f"[{h}] *missing*")
                    continue

                lines.append(f"[{h}] {item.axiom}")
                lines.extend(format_axiom_annotations(item.axiom))
        case EntitySelectionPage():
            for item in page.items:
                if not item.present:
                    lines.append(f"{item.iri} *missing*")
                    continue

                role_str = f" ({item.role})" if item.role else ""
                label_str = f" {dquoted(item.label)}" if item.label else ""
                lines.append(f"{item.iri}{role_str}{label_str}")

    return "\n".join(lines)


tool_read_selection = create_tool(
    read_selection, name="read_selection", annotations=ToolAnnotations(readOnlyHint=True)
)
