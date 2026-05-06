from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology
from ontoloom.prefixes import remove_prefix as core_remove_prefix

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, PrefixName


def remove_prefix(path: OntologyPath, name: PrefixName):
    """Remove a prefix mapping.

    Axioms that already reference `name:local_name` are not modified -> IRIs are
    stored as-is, so the existing data still works. Only future prefix expansion
    is affected.
    """
    with Ontology(path) as ont:
        core_remove_prefix(ont, name)
        return f"Removed prefix `{name}:`"


tool_remove_prefix = create_tool(
    remove_prefix, name="remove_prefix", annotations=ToolAnnotations(destructiveHint=True)
)
