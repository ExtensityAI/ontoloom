from mcp.types import ToolAnnotations
from ontoloom.ontology import axioms
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.types import LockedSelection

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import HexPrefix, OntologyPath


def rm_axioms(
    path: OntologyPath,
    hash_prefixes: list[HexPrefix] | None = None,
    within: LockedSelection | None = None,
):
    """Remove axioms by hash prefix or by selection.

    - `hash_prefixes`: Each prefix must uniquely match exactly one axiom.
      Atomic: if any prefix fails to resolve, nothing is removed.
    - `within`: Selection in `name@hash_prefix` form (e.g. "my_sel@a3f1"). The hash
      prefix verifies the selection hasn't changed since you last read it. Removes
      all axioms in this axiom selection. Best-effort: skips hashes no longer in DB.
      Mutually exclusive with hash_prefixes.
    """
    if within is not None and hash_prefixes is not None:
        msg = "Cannot use both 'within' and 'hash_prefixes'. Choose one."
        raise ValueError(msg)
    if within is None and hash_prefixes is None:
        msg = "Provide either 'hash_prefixes' or 'within'."
        raise ValueError(msg)

    with Ontology(path) as ont:
        if within is not None:
            removed, absent = axioms.remove_by_selection(ont, within)
            return (
                f"Removed {len(removed)} axioms ({absent} already absent). "
                f"Selection {within.name!r} retained."
            )

        result = axioms.remove_by_hash(ont, hash_prefixes)  # pyright: ignore[reportArgumentType]
        entries = [("-", ha) for ha in result.removed]
        return format_diff(entries, f"Removed {len(result.removed)} axioms.")


tool_rm_axioms = create_tool(
    rm_axioms, name="rm_axioms", annotations=ToolAnnotations(destructiveHint=True)
)
