from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.axioms.types import HashedAxiom
from ontoloom.connection import Ontology, session
from ontoloom.owl.iri import IRI
from ontoloom.query.constraints import (
    AxiomConstraint,
    HasAnyAnnotation,
    InAxiomSelection,
    InEntitySelection,
)
from ontoloom.query.dispatch import run
from ontoloom.query.list_axiom_hashes import ListAxiomHashes
from ontoloom.query.search_axioms import SearchAxioms
from ontoloom.selections.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.store import upsert_axiom_selection
from ontoloom.selections.types import (
    AxiomSelectionName,
    EntitySelectionName,
    ShowFilter,
)
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import (
    SELECT_INLINE_MAX,
    SELECT_PREVIEW,
    build_refs_per_axiom,
    format_axiom_listing,
    format_selection_result,
)
from ontoloom_mcp.components.locking import format_locked_quoted
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import Limit, OntologyPath


def search_axioms(
    path: OntologyPath,
    into: AxiomSelectionName,
    query: Annotated[str, MinLen(1)] | None = None,
    properties: Annotated[list[IRI], MinLen(1)] | None = None,
    within: AxiomSelectionName | EntitySelectionName | None = None,
    limit: Limit = 100,
):
    """Search axioms by axiom-level annotation text or property; save matches to a selection.

    Use `read_selection` to paginate the saved selection; combine with `match_axioms`
    via `within=` to narrow by structural shape.

    Args:
    - `into`: Kind-prefixed name for the output selection (e.g. `"axioms:todos"`).
    - `query`: Case-insensitive match on axiom-level annotation values. Exact matches
      rank before substring matches.
    - `properties`: Annotation property IRIs. With query, restricts text search to
      these properties; without query, finds axioms with any annotation whose
      property is in the set.
    - `within`: Restrict search to a named selection.
    - `limit`: Cap on inline page preview.
    """
    if query is None and properties is None:
        msg = "search_axioms requires at least one of `query` or `properties`."
        raise ValueError(msg)

    props_tuple = tuple(properties or ())
    scope: tuple[AxiomConstraint, ...] = (
        (InAxiomSelection(name=within),)
        if isinstance(within, AxiomSelectionName)
        else (InEntitySelection(name=within),)
        if isinstance(within, EntitySelectionName)
        else ()
    )

    ont = Ontology(path)
    with session(ont) as s:
        if query is None:
            hashes = run(
                s,
                ListAxiomHashes(
                    constraints=(HasAnyAnnotation(properties=props_tuple), *scope),
                ),
            )
        else:
            result = run(
                s,
                SearchAxioms(
                    query=query,
                    properties=props_tuple,
                    constraints=scope,
                ),
            )
            hashes = [hit.hash for hit in result.hits]

        source = _build_source(query, properties, within)
        upserted = upsert_axiom_selection(s, into.bare, hashes, source)
        sel = upserted.selection

        if not hashes:
            s.commit()
            return f"0 axioms -> {format_locked_quoted(sel)}.\nNo axioms found ({source})."

        page_size = sel.size if sel.size <= SELECT_INLINE_MAX else SELECT_PREVIEW
        page = run(
            s,
            ReadAxiomSelection(
                selection=AxiomSelectionName(f"axioms:{sel.name}"),
                limit=min(page_size, limit),
                offset=0,
                show=ShowFilter.ALL,
            ),
        )
        page_axioms = [
            HashedAxiom(axiom=item.axiom, hash=item.hash)
            for item in page.items
            if item.axiom is not None
        ]
        refs_per_axiom = build_refs_per_axiom(s, page_axioms)
        page_text = format_axiom_listing(page_axioms, refs_per_axiom=refs_per_axiom)
        s.commit()

    return format_selection_result("axioms", upserted, page_text)


def _build_source(
    query: str | None,
    properties: list[IRI] | None,
    within: AxiomSelectionName | EntitySelectionName | None,
) -> str:
    parts = []
    if query:
        parts.append(f"query={dquoted(query)}")
    if properties:
        parts.append(f"properties=[{', '.join(dquoted(str(p)) for p in properties)}]")
    if within is not None:
        parts.append(f"within={dquoted(str(within))}")
    return f"search_axioms({', '.join(parts)})"


tool_search_axioms = create_tool(
    search_axioms,
    name="search_axioms",
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
)
