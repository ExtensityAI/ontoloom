from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.store import OntologyStore

from ontoloom_mcp.components.formatting import format_search_axioms_page
from ontoloom_mcp.components.types import OntologyPath


def _search_axiom_annotations(
    path: OntologyPath,
    query: str,
    limit: int = 50,
    offset: int = 0,
):
    """Search for axioms by their annotation metadata (e.g. term type, source). Searches the `value` field of axiom-level annotations."""
    with OntologyStore(path) as store:
        page = store.search_axiom_annotations(query, limit=limit, offset=offset)
        if page.total == 0:
            return f'No axiom annotations matching "{query}".'
        return format_search_axioms_page(page.axioms, page.total, offset)


tool_search_axiom_annotations = Tool.from_function(
    _search_axiom_annotations,
    name="search_axiom_annotations",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
