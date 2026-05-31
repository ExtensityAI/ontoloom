from mcp.types import ToolAnnotations
from ontoloom.axioms.types import HashedAxiom
from ontoloom.connection import Ontology, session
from ontoloom.entities.reader import lookup_entity_labels
from ontoloom.query.dispatch import execute
from ontoloom.selections.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.read_entity_selection import ReadEntitySelection
from ontoloom.selections.store import axiom_selection_exists, entity_selection_exists
from ontoloom.selections.types import (
    AxiomSelectionPage,
    EntitySelectionPage,
    SelectionKind,
    SelectionName,
    SelectionNotFoundError,
    ShowFilter,
)

from ontoloom_mcp.components.formatting import (
    Ref,
    build_refs_per_axiom,
    format_axiom_listing,
    format_entity_line,
    format_missing_axiom_line,
    format_pagination,
    format_read_header,
)
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
            page_ax: AxiomSelectionPage = execute(
                s, ReadAxiomSelection(selection=name, limit=limit, offset=offset, show=show)
            )
            present_axioms = tuple(
                HashedAxiom(axiom=item.axiom, hash=item.hash)
                for item in page_ax.items
                if item.axiom is not None
            )
            refs_per_axiom = build_refs_per_axiom(s, present_axioms)
            s.commit()
            return _render_axiom_page(
                page_ax, present_axioms, refs_per_axiom, offset=offset, show=show
            )

        if entity_selection_exists(s, name):
            page_ent: EntitySelectionPage = execute(
                s, ReadEntitySelection(selection=name, limit=limit, offset=offset, show=show)
            )
            present_iris = [item.iri for item in page_ent.items if item.present]
            labels = lookup_entity_labels(s, present_iris)
            s.commit()
            return _render_entity_page(page_ent, labels, offset=offset, show=show)

        raise SelectionNotFoundError(name)


def _render_axiom_page(
    page: AxiomSelectionPage,
    present_axioms: tuple[HashedAxiom, ...],
    refs_per_axiom: list[list[Ref]],
    *,
    offset: int,
    show: ShowFilter,
):
    header = format_read_header(page.meta, page.present, page.missing)
    end = offset + len(page.items)
    pagination = format_pagination(
        offset + 1, end, page.total_filtered, SelectionKind.AXIOMS, filter=str(show)
    )

    if not page.items:
        return f"{header}\n{pagination}"

    refs_by_hash = {ha.hash: refs for ha, refs in zip(present_axioms, refs_per_axiom, strict=True)}
    body_lines: list[str] = []
    for item in page.items:
        if item.axiom is None:
            body_lines.append(format_missing_axiom_line(item.hash))
            continue

        ha = HashedAxiom(axiom=item.axiom, hash=item.hash)
        body_lines.append(format_axiom_listing([ha], refs_per_axiom=[refs_by_hash[item.hash]]))
    return f"{header}\n{pagination}\n\n" + "\n".join(body_lines)


def _render_entity_page(
    page: EntitySelectionPage,
    labels: dict[str, str | None],
    *,
    offset: int,
    show: ShowFilter,
):
    header = format_read_header(page.meta, page.present, page.missing)
    end = offset + len(page.items)
    pagination = format_pagination(
        offset + 1, end, page.total_filtered, SelectionKind.ENTITIES, filter=str(show)
    )

    if not page.items:
        return f"{header}\n{pagination}"

    body_lines: list[str] = []
    for item in page.items:
        if not item.present:
            body_lines.append(f"{item.iri} *missing*")
            continue

        body_lines.append(
            format_entity_line(Ref(iri=item.iri, label=labels.get(item.iri)), item.roles)
        )
    return f"{header}\n{pagination}\n\n" + "\n".join(body_lines)


tool_read_selection = create_tool(
    read_selection, name="read_selection", annotations=ToolAnnotations(readOnlyHint=True)
)
