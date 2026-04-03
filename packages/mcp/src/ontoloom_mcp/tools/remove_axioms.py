from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.store import OntologyStore

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.types import OntologyPath


def _remove_axioms(path: OntologyPath, prefixes: list[str]):
    """Remove axioms by hash prefix (from `get_axioms`). Each prefix must uniquely match exactly one axiom. Atomic: if any prefix fails to resolve, nothing is removed."""
    with OntologyStore(path) as store:
        try:
            result = store.remove_by_hash_prefix(prefixes)
        except ValueError as e:
            raise ToolError(str(e)) from e
        entries = [("-", ha) for ha in result.removed]
        return format_diff(entries, f"Removed {len(result.removed)} axioms.")


tool_remove_axioms = Tool.from_function(
    _remove_axioms,
    name="remove_axioms",
    annotations=ToolAnnotations(destructiveHint=True),
)
