from mcp.types import ToolAnnotations
from ontoloom.ontology import axioms, selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.literals import IRI
from ontoloom.ontology.types import SelectionKind

from ontoloom_mcp.components.formatting import (
    SELECT_INLINE_MAX,
    SELECT_PREVIEW,
    format_search_axioms_page,
    format_selection_result,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import Limit, OntologyPath, SelectionName


def search_axioms(
    path: OntologyPath,
    iri: IRI | None = None,
    axiom_types: list[str] | None = None,
    annotation_query: str | None = None,
    annotation_properties: list[str] | None = None,
    entity_query: str | None = None,
    within: SelectionName | None = None,
    select: SelectionName | None = None,
    limit: Limit = 50,
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
    - `within`: Scope to a named selection. Within an entity selection: only axioms
      mentioning those entities. Within an axiom selection: only those specific axioms.
    - `select`: Save ALL matching axiom hashes as a named selection. Returns all
      results regardless of limit/offset. Use `read_selection` to paginate afterwards.
    - `limit`/`offset`: Pagination (ignored when `select` is set).
    """
    with Ontology(path) as ont:
        kwargs = {
            "iri": iri,
            "axiom_types": axiom_types,
            "annotation_query": annotation_query,
            "annotation_properties": annotation_properties,
            "entity_query": entity_query,
            "within_selection": within,
        }

        if select is not None:
            hashes = axioms.collect_hashes(ont, **kwargs)
            source = _build_source(
                iri, axiom_types, annotation_query, annotation_properties, entity_query, within
            )
            content_hash, cardinality, old_cardinality = selections.write(
                ont, select, SelectionKind.AXIOMS, hashes, source
            )

            if not hashes:
                no_results = _no_results_msg(
                    iri, axiom_types, annotation_query, annotation_properties, entity_query, within
                )
                return f"0 axioms \u2192 {select!r} (sel@{content_hash}).\n{no_results}"

            limit_n = cardinality if cardinality <= SELECT_INLINE_MAX else SELECT_PREVIEW
            display_total = cardinality
            page = axioms.search(ont, **kwargs, limit=limit_n, offset=0)
            page_text = format_search_axioms_page(page.axioms, display_total, 0)

            return format_selection_result(
                "axioms", select, content_hash, cardinality, old_cardinality, page_text
            )

        page = axioms.search(ont, **kwargs, limit=limit, offset=offset)
        if page.total == 0:
            return _no_results_msg(
                iri, axiom_types, annotation_query, annotation_properties, entity_query, within
            )
        return format_search_axioms_page(page.axioms, page.total, offset)


def _no_results_msg(
    iri, axiom_types, annotation_query, annotation_properties, entity_query, within
):
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
    if within:
        parts.append(f"within={within!r}")
    filter_desc = ", ".join(parts) if parts else "no filters"
    return f"No axioms found ({filter_desc})."


def _build_source(iri, axiom_types, annotation_query, annotation_properties, entity_query, within):
    parts = []
    if iri:
        parts.append(f"iri={iri!r}")
    if axiom_types:
        parts.append(f"axiom_types={axiom_types}")
    if annotation_query:
        parts.append(f"annotation_query={annotation_query!r}")
    if annotation_properties:
        parts.append(f"annotation_properties={annotation_properties}")
    if entity_query:
        parts.append(f"entity_query={entity_query!r}")
    if within:
        parts.append(f"within={within!r}")
    return f"search_axioms({', '.join(parts)})"


tool_search_axioms = create_tool(
    search_axioms,
    name="search_axioms",
    # readOnlyHint: selections are ephemeral working sets, not ontology data
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
