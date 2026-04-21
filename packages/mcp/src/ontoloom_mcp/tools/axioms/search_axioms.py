from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.models.literals import IRI
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.formatting import format_search_axioms_page
from ontoloom_mcp.components.types import OntologyPath

_SELECT_PREVIEW = 5
_SELECT_INLINE_MAX = 20


@handle_tool_errors
def _search_axioms(
    path: OntologyPath,
    iri: str = "",
    axiom_types: list[str] = [],  # noqa: B006
    annotation_query: str = "",
    annotation_properties: list[str] = [],  # noqa: B006
    entity_query: str = "",
    within: str = "",
    select: str = "",
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
    - `within`: Scope search to an existing selection (name only). If kind='entities',
      restricts to axioms mentioning those entities. If kind='axioms', restricts to
      those specific axioms.
    - `select`: Save ALL matching axiom hashes to a selection with this name.
      Incompatible with limit/offset. Use `read_selection` to paginate saved results.
    - `limit`/`offset`: Pagination (incompatible with `select`).
    """
    if select and "@" in select:
        msg = "Selection names must not contain '@'."
        raise ValueError(msg)
    if select and (limit != 50 or offset != 0):
        msg = "limit/offset are incompatible with select. Use read_selection to paginate saved results."
        raise ValueError(msg)

    with OntologyStore(path) as store:
        kwargs = {
            "iri": IRI(iri) if iri else None,
            "axiom_types": axiom_types or None,
            "annotation_query": annotation_query or None,
            "annotation_properties": annotation_properties or None,
            "entity_query": entity_query or None,
            "within": within or None,
        }

        if select:
            # Collect all hashes and save to selection
            hashes = store.collect_axiom_hashes(**kwargs)
            if not hashes:
                return _no_results_msg(
                    iri, axiom_types, annotation_query, annotation_properties, entity_query, within
                )

            source = _build_source(
                iri, axiom_types, annotation_query, annotation_properties, entity_query, within
            )
            content_hash, cardinality, old_cardinality = store._write_selection(
                select, "axioms", hashes, source
            )

            parts = [f"{cardinality} axioms \u2192 {select!r} (sel@{content_hash})."]
            if old_cardinality is not None:
                parts.append(f"Overwrote previous ({old_cardinality} items).")

            if cardinality <= _SELECT_INLINE_MAX:
                # Show all inline
                page = store.search_axioms(**kwargs, limit=cardinality, offset=0)
                parts.append("")
                parts.append(format_search_axioms_page(page.axioms, page.total, 0))
            else:
                # Show preview
                page = store.search_axioms(**kwargs, limit=_SELECT_PREVIEW, offset=0)
                parts.append(f"Preview (first {_SELECT_PREVIEW}):")
                parts.append("")
                parts.append(format_search_axioms_page(page.axioms, cardinality, 0))
                parts.append(
                    f"\nUse read_selection(name={select!r}) to browse all {cardinality} results."
                )

            return "\n".join(parts)

        # Normal paginated search
        page = store.search_axioms(**kwargs, limit=limit, offset=offset)
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


tool_search_axioms = Tool.from_function(
    _search_axioms,
    name="search_axioms",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
