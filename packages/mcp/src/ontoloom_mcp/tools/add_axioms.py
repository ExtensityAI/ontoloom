from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.models.axioms import Axiom
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.types import OntologyPath


def _add_axioms(path: OntologyPath, axioms: list[Axiom]):
    """Add axioms to an existing ontology. Duplicates are skipped. Returns a diff: `+` = added, `=` = skipped."""
    with OntologyStore(path) as store:
        result = store.add_axioms(axioms)
        entries = [("+", ha) for ha in result.added] + [("=", ha) for ha in result.skipped]
        return format_diff(
            entries,
            f"Added {len(result.added)}, skipped {len(result.skipped)} axioms.",
        )


tool_add_axioms = Tool.from_function(
    _add_axioms, name="add_axioms", annotations=ToolAnnotations(idempotentHint=True)
)
