from mcp.types import ToolAnnotations
from ontoloom.ontology import prefixes
from ontoloom.ontology.connection import Ontology

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def rm_prefix(path: OntologyPath, name: str):
    """Remove a prefix mapping."""
    with Ontology(path) as ont:
        prefixes.remove(ont, name)
        return f"Removed prefix `{name}:`"


tool_rm_prefix = create_tool(
    rm_prefix, name="rm_prefix", annotations=ToolAnnotations(destructiveHint=True)
)
