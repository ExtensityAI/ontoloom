from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from ontoloom.core.ontology.models.ontology import Ontology

from ontoloom_mcp.components.ontology_file import OntologyPath


def _create_ontology(path: OntologyPath):
    """Create a new empty OWL 2 EL ontology file. Fails if the file already exists."""
    if path.exists():
        msg = f"'{path}' already exists. Use a different path or load the existing ontology."
        raise ToolError(msg)

    if not path.parent.exists():
        msg = f"Parent directory '{path.parent}' does not exist. Please create it first."
        raise ToolError(msg)

    ontology = Ontology(axioms=())
    path.write_text(ontology.model_dump_json(indent=2) + "\n")
    return f"Created ontology at `{path}`."


tool_create_ontology = Tool.from_function(_create_ontology, name="create_ontology")
