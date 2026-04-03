from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.models.literals import IRI
from ontoloom.core.ontology.store import OntologyStore

from ontoloom_mcp.components.formatting import format_search_axioms_page
from ontoloom_mcp.components.types import OntologyPath


def _search_axioms(
    path: OntologyPath,
    iri: IRI | None = None,
    axiom_types: list[str] | None = None,
    annotation_query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """Search and filter axioms. All parameters optional — no filters lists all axioms.

    - `iri`: Only axioms mentioning this entity.
    - `axiom_types`: Only axioms of these types (e.g. ["SubClassOf", "Declaration"]).
    - `annotation_query`: Substring match on axiom-level annotation values.
    - `limit`/`offset`: Pagination.
    """
    with OntologyStore(path) as store:
        page = store.search_axioms(
            iri=iri,
            axiom_types=axiom_types,
            annotation_query=annotation_query,
            limit=limit,
            offset=offset,
        )
        if page.total == 0:
            parts = []
            if iri:
                parts.append(f"iri={iri}")
            if axiom_types:
                parts.append(f"types={axiom_types}")
            if annotation_query:
                parts.append(f"annotation={annotation_query!r}")
            filter_desc = ", ".join(parts) if parts else "no filters"
            return f"No axioms found ({filter_desc})."
        return format_search_axioms_page(page.axioms, page.total, offset)


tool_search_axioms = Tool.from_function(
    _search_axioms,
    name="search_axioms",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
