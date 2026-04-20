from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.formatting import (
    format_axiom_summary_from_counter,
    format_entity_summary,
)
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _describe_ontology(path: OntologyPath):
    """Get entity counts, axiom counts, and prefix mappings for an ontology."""
    with OntologyStore(path) as store:
        axiom_counts = store.axiom_summary()
        total_entities, role_counts = store.entity_summary()
        prefixes = store.list_prefixes()

        parts = []
        parts.append(format_entity_summary(total_entities, role_counts))
        parts.append(format_axiom_summary_from_counter(axiom_counts))

        if prefixes:
            prefix_lines = ["Prefixes:"]
            for name, iri in sorted(prefixes.items()):
                prefix_lines.append(f"  {name}: \u2192 {iri}")
            parts.append("\n".join(prefix_lines))
        else:
            parts.append("No prefixes defined.")

        return "\n\n".join(parts)


tool_describe_ontology = Tool.from_function(
    _describe_ontology,
    name="describe_ontology",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
