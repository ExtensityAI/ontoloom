from typing import Literal

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.formatting import format_entity_search_page
from ontoloom_mcp.components.types import OntologyPath

Role = Literal[
    "Class",
    "ObjectProperty",
    "DataProperty",
    "AnnotationProperty",
    "NamedIndividual",
    "Datatype",
]


@handle_tool_errors
def _search_entities(
    path: OntologyPath,
    query: str = "",
    role: Role | str = "",
    namespace: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """Search and filter entities. All parameters optional — no filters lists all entities.

    - `query`: Substring match on IRI local names and annotation values (labels, comments).
    - `role`: Filter by entity type: "Class", "ObjectProperty", "DataProperty", "AnnotationProperty", "NamedIndividual", "Datatype".
    - `namespace`: Filter by IRI prefix (e.g. "ex", "snomed").
    - `limit`/`offset`: Pagination.
    """
    with OntologyStore(path) as store:
        page = store.search_entities(
            query=query or None,
            role=role or None,
            namespace=namespace or None,
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
