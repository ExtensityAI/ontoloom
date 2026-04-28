from mcp.types import ToolAnnotations
from ontoloom.ontology import prefixes
from ontoloom.ontology.connection import Ontology

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, PrefixName


def set_prefix(path: OntologyPath, name: PrefixName, iri: str):
    """Add or update a prefix mapping (e.g. name="ex", iri="http://example.org/").

    Prefixes expand the `prefix:local_name` shorthand used in entity IRIs (e.g.
    `ex:Dog` -> `http://example.org/Dog`). Idempotent — overwriting an existing
    prefix does not affect axioms already stored with that prefix string.
    """
    with Ontology(path) as ont:
        prefixes.set(ont, name, iri)
        return f"Set prefix `{name}:` \u2192 `{iri}`"


tool_set_prefix = create_tool(
    set_prefix, name="set_prefix", annotations=ToolAnnotations(idempotentHint=True)
)
