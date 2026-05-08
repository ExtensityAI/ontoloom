from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology
from ontoloom.hashing import HASH_DISPLAY_LEN
from ontoloom.selections.store import read_selection as core_read_selection
from ontoloom.selections.types import SelectionKind, ShowFilter
from ontoloom.transactions import session

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import Limit, Offset, OntologyPath, SelectionName


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
        result = core_read_selection(s, name, limit=limit, offset=offset, show=show)
        s.commit()

    meta = result.meta
    header = (
        f"Selection {meta.locked!r} ({meta.kind}): "
        f"{meta.size} total ({result.present} present, {result.missing} missing)"
    )

    end = offset + len(result.items)
    if not result.items:
        showing = f"0 results (filter: {show})."
    else:
        showing = f"Showing {offset + 1}-{end} of {result.total_filtered} (filter: {show}):"

    lines = [header, showing, ""]

    if meta.kind == SelectionKind.AXIOMS:
        for item in result.items:
            h = item.key[:HASH_DISPLAY_LEN]
            if item.missing:
                lines.append(f"[{h}] *missing*")
            else:
                lines.append(f"[{h}] {item.axiom}")
    else:
        for item in result.items:
            if item.missing:
                lines.append(f"{item.key} *missing*")
            else:
                role_str = f" ({item.role})" if item.role else ""
                label_str = f' "{item.label}"' if item.label else ""
                lines.append(f"{item.key}{role_str}{label_str}")

    return "\n".join(lines)


tool_read_selection = create_tool(
    read_selection, name="read_selection", annotations=ToolAnnotations(readOnlyHint=True)
)
