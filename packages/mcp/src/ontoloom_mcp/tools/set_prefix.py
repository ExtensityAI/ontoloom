from fastmcp.tools import Tool
from ontoloom.core.ontology.store import OntologyStore

from ontoloom_mcp.components.types import OntologyPath


def _set_prefix(path: OntologyPath, name: str, iri: str) -> str:
    """Add or update a prefix mapping (e.g. name="ex", iri="http://example.org/")."""
    with OntologyStore(path) as store:
        store.set_prefix(name, iri)
        return f"Set prefix `{name}:` \u2192 `{iri}`"


tool_set_prefix = Tool.from_function(_set_prefix, name="set_prefix")
