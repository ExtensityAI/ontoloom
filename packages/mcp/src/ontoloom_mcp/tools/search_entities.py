from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.formatting import format_entity_search_page
from ontoloom_mcp.components.types import OntologyPath


def _search_entities(
    path: OntologyPath,
    query: str | None = None,
    role: str | None = None,
    namespace: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """Search and filter entities. All parameters optional — no filters lists all entities.

    - `query`: Substring match on IRI local names and annotation values (labels, comments).
    - `role`: Filter by entity type (e.g. "Class", "ObjectProperty").
    - `namespace`: Filter by IRI prefix (e.g. "ex", "snomed").
    - `limit`/`offset`: Pagination.
    """
    with OntologyStore(path) as store:
        page = store.search_entities(
            query=query,
            role=role,
            namespace=namespace,
            limit=limit,
            offset=offset,
        )
        if page.total == 0:
            parts = []
            if query:
                parts.append(f"query={query!r}")
            if role:
                parts.append(f"role={role}")
            if namespace:
                parts.append(f"namespace={namespace}")
            filter_desc = ", ".join(parts) if parts else "no filters"
            return f"No entities found ({filter_desc})."
        return format_entity_search_page(page.matches, page.total, offset)


tool_search_entities = Tool.from_function(
    _search_entities,
    name="search_entities",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
