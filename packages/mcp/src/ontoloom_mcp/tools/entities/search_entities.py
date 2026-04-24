from mcp.types import ToolAnnotations
from ontoloom.ontology import entities, selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.base import EntityType
from ontoloom.ontology.types import SelectionKind

from ontoloom_mcp.components.formatting import (
    SELECT_INLINE_MAX,
    SELECT_PREVIEW,
    format_entity_search_page,
    format_selection_result,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import Limit, OntologyPath, SelectionName


def search_entities(
    path: OntologyPath,
    query: str | None = None,
    role: EntityType | None = None,
    namespace: str | None = None,
    within: SelectionName | None = None,
    select: SelectionName | None = None,
    limit: Limit = 50,
    offset: int = 0,
):
    """Search and filter entities. All parameters optional — no filters lists all entities.

    - `query`: Substring match on IRI local names and annotation values (labels, comments).
    - `role`: Filter by entity type: "Class", "ObjectProperty", "DataProperty",
      "AnnotationProperty", "NamedIndividual", "Datatype".
    - `namespace`: Filter by IRI prefix (e.g. "ex", "snomed").
    - `within`: Scope to a named selection. Within an entity selection: only those
      specific entities. Within an axiom selection: only entities mentioned in those axioms.
    - `select`: Save ALL matching entity IRIs as a named selection. Returns all
      results regardless of limit/offset. Use `read_selection` to paginate afterwards.
    - `limit`/`offset`: Pagination (ignored when `select` is set).
    """
    with Ontology(path) as ont:
        kwargs = {
            "query": query,
            "role": role,
            "namespace": namespace,
            "within_selection": within,
        }

        if select is not None:
            iris = entities.collect_iris(ont, **kwargs)
            source = _build_source(query, role, namespace, within)
            content_hash, cardinality, old_cardinality = selections.write(
                ont, select, SelectionKind.ENTITIES, iris, source
            )

            if not iris:
                no_results = _no_results_msg(query, role, namespace, within)
                return f"0 entities \u2192 {select!r} (sel@{content_hash}).\n{no_results}"

            limit_n = cardinality if cardinality <= SELECT_INLINE_MAX else SELECT_PREVIEW
            display_total = cardinality
            page = entities.search(ont, **kwargs, limit=limit_n, offset=0)
            page_text = format_entity_search_page(page.matches, display_total, 0)

            return format_selection_result(
                "entities", select, content_hash, cardinality, old_cardinality, page_text
            )

        page = entities.search(ont, **kwargs, limit=limit, offset=offset)
        if page.total == 0:
            return _no_results_msg(query, role, namespace, within)
        return format_entity_search_page(page.matches, page.total, offset)


def _no_results_msg(query, role, namespace, within):
    parts = []
    if query:
        parts.append(f"query={query!r}")
    if role:
        parts.append(f"role={role}")
    if namespace:
        parts.append(f"namespace={namespace}")
    if within:
        parts.append(f"within={within!r}")
    filter_desc = ", ".join(parts) if parts else "no filters"
    return f"No entities found ({filter_desc})."


def _build_source(query, role, namespace, within):
    parts = []
    if query:
        parts.append(f"query={query!r}")
    if role:
        parts.append(f"role={role!r}")
    if namespace:
        parts.append(f"namespace={namespace!r}")
    if within:
        parts.append(f"within={within!r}")
    return f"search_entities({', '.join(parts)})"


tool_search_entities = create_tool(
    search_entities,
    name="search_entities",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
