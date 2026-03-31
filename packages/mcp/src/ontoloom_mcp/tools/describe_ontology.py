from fastmcp.tools import Tool
from mcp.types import ToolAnnotations

from ontoloom_mcp.components.formatting import format_axiom_summary
from ontoloom_mcp.components.ontology_file import OntologyPath, open_ontology


def _describe_ontology(path: OntologyPath):
    """Get axiom count statistics for an ontology. Returns total count and breakdown by axiom type."""
    with open_ontology(path) as (ontology, _):
        return format_axiom_summary(ontology.axioms)


tool_describe_ontology = Tool.from_function(
    _describe_ontology,
    name="describe_ontology",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
