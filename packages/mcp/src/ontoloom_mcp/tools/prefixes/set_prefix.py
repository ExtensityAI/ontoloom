from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _set_prefix(path: OntologyPath, name: str, iri: str):
    """Add or update a prefix mapping (e.g. name="ex", iri="http://example.org/")."""
    with OntologyStore(path) as store:
        store.set_prefix(name, iri)
        return f"Set prefix `{name}:` \u2192 `{iri}`"


tool_set_prefix = Tool.from_function(
    _set_prefix,
    name="set_prefix",
    annotations=ToolAnnotations(idempotentHint=True),
)
