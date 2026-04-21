from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _remove_axioms(
    path: OntologyPath,
    hash_prefixes: list[str] = [],  # noqa: B006
    select: str = "",
):
    """Remove axioms by hash prefix or by selection.

    - `hash_prefixes`: Each prefix must uniquely match exactly one axiom.
      Atomic: if any prefix fails to resolve, nothing is removed.
    - `select`: Format "name@hash_prefix". Remove all axioms in this axiom selection.
      Best-effort: skips hashes no longer in DB. Mutually exclusive with hash_prefixes.
    """
    if select and hash_prefixes:
        msg = "Cannot use both 'select' and 'hash_prefixes'. Choose one."
        raise ValueError(msg)
    if not select and not hash_prefixes:
        msg = "Provide either 'hash_prefixes' or 'select'."
        raise ValueError(msg)

    with OntologyStore(path) as store:
        if select:
            if "@" not in select:
                msg = "select must be in format 'name@hash_prefix' for write operations."
                raise ValueError(msg)
            name, hash_prefix = select.rsplit("@", 1)
            removed, absent = store.remove_by_selection(name, hash_prefix)
            return (
                f"Removed {len(removed)} axioms ({absent} already absent). "
                f"Selection {name!r} retained."
            )

        result = store.remove_by_hash_prefix(hash_prefixes)
        entries = [("-", ha) for ha in result.removed]
        return format_diff(entries, f"Removed {len(result.removed)} axioms.")


tool_remove_axioms = Tool.from_function(
    _remove_axioms,
    name="remove_axioms",
    annotations=ToolAnnotations(destructiveHint=True),
)
