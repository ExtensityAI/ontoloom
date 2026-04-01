from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.operations import remove_axioms

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.hashing import compute_hashes, resolve_or_raise
from ontoloom_mcp.components.ontology_file import OntologyPath, open_ontology


def _remove_axioms(path: OntologyPath, prefixes: list[str]):
    """Remove axioms by hash prefix (from `search_axioms`). Each prefix must uniquely match exactly one axiom. Atomic: if any prefix fails to resolve, nothing is removed."""
    with open_ontology(path, write=True) as (ontology, save):
        hashed = compute_hashes(ontology.axioms)
        matches = resolve_or_raise(hashed, prefixes)

        to_remove = {m.axiom for m in matches}  # pyright: ignore[reportUnhashable] -- axioms are hashable
        new_ontology, result = remove_axioms(ontology, to_remove)

        if result.removed:
            save(new_ontology)

        removed_lookup = {ha.axiom: ha for ha in hashed if ha.axiom in to_remove}
        entries = [("-", removed_lookup[a]) for a in result.removed]
        return format_diff(
            entries,
            f"Removed {len(result.removed)}, total {len(new_ontology.axioms)} axioms.",
        )


tool_remove_axioms = Tool.from_function(
    _remove_axioms,
    name="remove_axioms",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True),
)
