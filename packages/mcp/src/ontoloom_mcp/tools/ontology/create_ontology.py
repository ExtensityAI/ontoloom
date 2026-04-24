from mcp.types import ToolAnnotations
from ontoloom.ontology.connection import Ontology

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def create_ontology(path: OntologyPath):
    """Create a new empty OWL 2 EL ontology database. Fails if the file already exists."""
    Ontology.create(path)
    return f"Created ontology at `{path}`."


tool_create_ontology = create_tool(
    create_ontology, name="create_ontology", annotations=ToolAnnotations(idempotentHint=False)
)
