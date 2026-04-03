from fastmcp.tools import Tool
from ontoloom.core.ontology.store import OntologyStore

from ontoloom_mcp.components.types import OntologyPath


def _create_ontology(path: OntologyPath):
    """Create a new empty OWL 2 EL ontology database. Fails if the file already exists."""
    OntologyStore.create(path)
    return f"Created ontology at `{path}`."


tool_create_ontology = Tool.from_function(_create_ontology, name="create_ontology")
