from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _create_ontology(path: OntologyPath):
    """Create a new empty OWL 2 EL ontology database. Fails if the file already exists."""
    OntologyStore.create(path)
    return f"Created ontology at `{path}`."


tool_create_ontology = Tool.from_function(
    _create_ontology,
    name="create_ontology",
    annotations=ToolAnnotations(idempotentHint=False),
)
