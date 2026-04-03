from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.store import OntologyStore

from ontoloom_mcp.components.formatting import (
    format_axiom_summary_from_counter,
    format_entity_summary,
)
from ontoloom_mcp.components.types import OntologyPath


def _describe_ontology(path: OntologyPath):
    """Get entity and axiom count statistics for an ontology."""
    with OntologyStore(path) as store:
        axiom_counts = store.axiom_summary()
        total_entities, role_counts = store.entity_summary()
        entity_part = format_entity_summary(total_entities, role_counts)
        axiom_part = format_axiom_summary_from_counter(axiom_counts)
        return f"{entity_part}\n\n{axiom_part}"


tool_describe_ontology = Tool.from_function(
    _describe_ontology,
    name="describe_ontology",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
