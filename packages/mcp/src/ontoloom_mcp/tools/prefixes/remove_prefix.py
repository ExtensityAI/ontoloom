from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.prefixes.store import remove_prefix as core_remove_prefix
from ontoloom.prefixes.types import PrefixName

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def remove_prefix(path: OntologyPath, name: PrefixName):
    """Remove a prefix mapping. Refuses if any entity still uses the prefix."""
    ont = Ontology(path)
    with session(ont) as s:
        core_remove_prefix(s, name)
        s.commit()

    return f"Removed prefix `{name}:`"


tool_remove_prefix = create_tool(
    remove_prefix, name="remove_prefix", annotations=ToolAnnotations(destructiveHint=True)
)
