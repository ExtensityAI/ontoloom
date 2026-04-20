from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.models.literals import IRI
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.formatting import format_search_axioms_page
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _search_axioms(
    path: OntologyPath,
    iri: str = "",
    axiom_types: list[str] = [],  # noqa: B006
    annotation_query: str = "",
    annotation_properties: list[str] = [],  # noqa: B006
    entity_query: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """Search and filter axioms. All parameters optional — no filters lists all axioms.

    - `iri`: Only axioms mentioning this entity (e.g. ":Dog", "ex:hasPart").
    - `axiom_types`: Only axioms of these types (e.g. ["SubClassOf", "Declaration"]).
    - `annotation_query`: Substring match on axiom-level annotation values.
    - `annotation_properties`: Only AnnotationAssertion axioms using these properties
      (e.g. ["oboInOwl:hasExactSynonym", "rdfs:label"]).
    - `entity_query`: Only axioms mentioning entities whose annotations match this
      substring. Note: matches any position — e.g., a SubClassOf(A, B) is returned
      if B matches, not just if A matches.
    - `limit`/`offset`: Pagination.
    """
    with OntologyStore(path) as store:
        page = store.search_axioms(
            iri=IRI(iri) if iri else None,
            axiom_types=axiom_types or None,
            annotation_query=annotation_query or None,
            annotation_properties=annotation_properties or None,
            entity_query=entity_query or None,
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
            if annotation_properties:
                parts.append(f"properties={annotation_properties}")
            if entity_query:
                parts.append(f"entity_query={entity_query!r}")
            filter_desc = ", ".join(parts) if parts else "no filters"
            return f"No axioms found ({filter_desc})."
        return format_search_axioms_page(page.axioms, page.total, offset)


tool_search_axioms = Tool.from_function(
    _search_axioms,
    name="search_axioms",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
