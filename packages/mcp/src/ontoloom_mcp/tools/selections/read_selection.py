from mcp.types import ToolAnnotations
from ontoloom.axioms.hashing import short_hash
from ontoloom.connection import Ontology, session
from ontoloom.query.dispatch import run
from ontoloom.selections.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.read_entity_selection import ReadEntitySelection
from ontoloom.selections.store import axiom_selection_exists, entity_selection_exists
from ontoloom.selections.types import (
    AxiomSelectionPage,
    EntitySelectionPage,
    SelectionName,
    SelectionNotFoundError,
    ShowFilter,
)
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import format_axiom_annotations, format_selection_ref
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

    - `name`: Selection name (e.g. `"my_sel"`). The kind (axioms or entities)
      is resolved by lookup.
    - `show`: "all" (default), "present" (only items still in ontology),
      "missing" (only items removed since the selection was created).
      Use "missing" to audit a selection after ontology modifications.

    Always includes summary stats (total, present, missing) regardless of filter.
    Pagination applies after the show filter. For bulk verification, dispatch a
    subagent to paginate rather than reading everything into your context.
    """
    ont = Ontology(path)
    with session(ont) as s:
        if axiom_selection_exists(s, name):
            page_ax: AxiomSelectionPage = run(
                s, ReadAxiomSelection(selection=name, limit=limit, offset=offset, show=show)
            )
            s.commit()
            return _format_axiom_page(page_ax, offset=offset, show=show)

        if entity_selection_exists(s, name):
            page_ent: EntitySelectionPage = run(
                s, ReadEntitySelection(selection=name, limit=limit, offset=offset, show=show)
            )
            s.commit()
            return _format_entity_page(page_ent, offset=offset, show=show)

        raise SelectionNotFoundError(name)


def _format_axiom_page(page: AxiomSelectionPage, *, offset: int, show: ShowFilter):
    meta = page.meta
    header = (
        f"Selection {format_selection_ref(meta)} (axioms): "
        f"{meta.size} total ({page.present} present, {page.missing} missing)"
    )

    end = offset + len(page.items)
    if not page.items:
        showing = f"0 results (filter: {show})."
    else:
        showing = f"Showing {offset + 1}-{end} of {page.total_filtered} (filter: {show}):"

    lines = [header, showing, ""]
    for item in page.items:
        h = short_hash(item.hash)

        if item.axiom is None:
            lines.append(f"[{h}] *missing*")
            continue

        lines.append(f"[{h}] {item.axiom}")
        lines.extend(format_axiom_annotations(item.axiom))
    return "\n".join(lines)


def _format_entity_page(page: EntitySelectionPage, *, offset: int, show: ShowFilter):
    meta = page.meta
    header = (
        f"Selection {format_selection_ref(meta)} (entities): "
        f"{meta.size} total ({page.present} present, {page.missing} missing)"
    )

    end = offset + len(page.items)
    if not page.items:
        showing = f"0 results (filter: {show})."
    else:
        showing = f"Showing {offset + 1}-{end} of {page.total_filtered} (filter: {show}):"

    lines = [header, showing, ""]
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
