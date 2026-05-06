from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology
from ontoloom.prefixes import set_prefix as core_set_prefix

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, PrefixName


def set_prefix(path: OntologyPath, name: PrefixName, iri: str):
    """Add or update a prefix mapping (e.g. name="ex", iri="http://example.org/").

    Prefixes expand the `prefix:local_name` shorthand used in entity IRIs (e.g.
    `ex:Dog` -> `http://example.org/Dog`). Idempotent -> overwriting an existing
    prefix does not affect axioms already stored with that prefix string.
    """
    with Ontology(path) as ont:
        core_set_prefix(ont, name, iri)
        return f"Set prefix `{name}:` -> `{iri}`"


tool_set_prefix = create_tool(
    set_prefix, name="set_prefix", annotations=ToolAnnotations(idempotentHint=True)
)
