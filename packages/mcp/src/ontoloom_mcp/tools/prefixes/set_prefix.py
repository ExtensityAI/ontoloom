from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology
from ontoloom.prefixes import set_prefix as core_set_prefix

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, PrefixName


def set_prefix(path: OntologyPath, name: PrefixName, iri: str, force: bool = False):
    """Add or update a prefix mapping (e.g. name="ex", iri="http://example.org/").

    Prefixes expand the `prefix:local_name` shorthand used in entity IRIs (e.g.
    `ex:Dog` -> `http://example.org/Dog`). Refuses to reassign a prefix already
    used by stored axioms (which would silently change their meaning); pass
    `force=true` to override.
    """
    with Ontology(path) as ont:
        result = core_set_prefix(ont, name, iri, force=force)

        if result.previous_iri is None:
            return f"Set prefix `{name}:` -> `{iri}`"

        if result.previous_iri == iri:
            return f"Set prefix `{name}:` -> `{iri}` (unchanged)"

        suffix = f"; {result.in_use_count} entities affected" if result.in_use_count > 0 else ""
        return f"Set prefix `{name}:` -> `{iri}` (was `{result.previous_iri}`{suffix})"


tool_set_prefix = create_tool(
    set_prefix, name="set_prefix", annotations=ToolAnnotations(idempotentHint=True)
)
