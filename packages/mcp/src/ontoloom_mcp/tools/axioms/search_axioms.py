from collections.abc import Sequence
from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.owl.iri import IRI
from ontoloom.query.constraints import (
    AxiomConstraint,
    HasAnyAnnotation,
)
from ontoloom.query.dispatch import resolve_within, run
from ontoloom.query.list_axiom_hashes import ListAxiomHashes
from ontoloom.query.search_axioms import SearchAxioms
from ontoloom.selections.store import upsert_axiom_selection
from ontoloom.selections.types import SelectionName, WriteMode
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import format_selection_ref, format_selection_result
from ontoloom_mcp.components.preview import format_axiom_selection_preview
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import Limit, OntologyPath


def search_axioms(
    path: OntologyPath,
    into: SelectionName,
    mode: WriteMode = WriteMode.CREATE,
    query: Annotated[str, MinLen(1)] | None = None,
    properties: Annotated[list[IRI], MinLen(1)] | None = None,
    within: SelectionName | None = None,
    limit: Limit = 100,
):
    """Search axioms by axiom-level annotation text or property; save matches to a selection.

    Use `read_selection` to paginate the saved selection; combine with `match_axioms`
    via `within=` to narrow by structural shape.

    Args:
    - `into`: Name for the output selection (e.g. `"todos"`).
    - `mode`: `create` (default) refuses if the selection name already exists; `replace` overwrites it.
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

    ont = Ontology(path)
    with session(ont) as s:
        scope: tuple[AxiomConstraint, ...] = (
            (resolve_within(s, within),) if within is not None else ()
        )

        if query is None:
            hashes = run(
                s,
                ListAxiomHashes(
                    constraints=(HasAnyAnnotation(properties=props_tuple), *scope),
                ),
            )
        else:
            hashes = run(
                s,
                SearchAxioms(
                    query=query,
                    properties=props_tuple,
                    constraints=scope,
                ),
            )

        source = _build_source(query, props_tuple, within)
        upserted = upsert_axiom_selection(s, into, hashes, source, mode=mode)
        sel = upserted.selection

        if not hashes:
            s.commit()
            return f"0 axioms -> {format_selection_ref(sel)}.\nNo axioms found ({source})."

        page_text = format_axiom_selection_preview(s, upserted, limit=limit)
        s.commit()

    return format_selection_result(upserted, page_text)


def _build_source(
    query: str | None,
    properties: Sequence[IRI],
    within: SelectionName | None,
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
