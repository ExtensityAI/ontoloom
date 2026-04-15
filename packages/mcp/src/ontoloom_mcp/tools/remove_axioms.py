from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.types import OntologyPath


def _remove_axioms(path: OntologyPath, hash_prefixes: list[str]):
    """Remove axioms by hash prefix (from `search_axioms`). Each prefix must uniquely match exactly one axiom. Atomic: if any prefix fails to resolve, nothing is removed."""
    with OntologyStore(path) as store:
        try:
            result = store.remove_by_hash_prefix(hash_prefixes)
        except ValueError as e:
            raise ToolError(str(e)) from e
        entries = [("-", ha) for ha in result.removed]
        return format_diff(entries, f"Removed {len(result.removed)} axioms.")


tool_remove_axioms = Tool.from_function(
    _remove_axioms,
    name="remove_axioms",
    annotations=ToolAnnotations(destructiveHint=True),
)
