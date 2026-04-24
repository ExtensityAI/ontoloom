from mcp.types import ToolAnnotations
from ontoloom.ontology.axioms import add
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.axioms import Axiom

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def add_axioms(path: OntologyPath, axioms: list[Axiom]):
    """Add axioms to an existing ontology. Duplicates are skipped. Returns a diff: `+` = added, `=` = skipped."""
    with Ontology(path) as ont:
        result = add(ont, axioms)
        entries = [("+", ha) for ha in result.added] + [("=", ha) for ha in result.skipped]
        return format_diff(
            entries,
            f"Added {len(result.added)}, skipped {len(result.skipped)} axioms.",
        )


tool_add_axioms = create_tool(
    add_axioms, name="add_axioms", annotations=ToolAnnotations(idempotentHint=True)
)
