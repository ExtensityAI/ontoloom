from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.axioms.store import remove_axioms_by_hash, remove_axioms_by_selection
from ontoloom.connection import Ontology
from ontoloom.selections.types import LockedSelection
from ontoloom.transactions import session

from ontoloom_mcp.components.errors import MissingRequiredError, MutuallyExclusiveError
from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import HexPrefix, OntologyPath


def remove_axioms(
    path: OntologyPath,
    axiom_hashes: Annotated[list[HexPrefix], MinLen(1)] | None = None,
    within: LockedSelection | None = None,
):
    """Remove axioms by hash prefix or by selection.

    - `axiom_hashes`: Each hash (full or unambiguous prefix) must match exactly one
      axiom. Atomic: if any hash fails to resolve, nothing is removed.
    - `within`: Selection in `name@hash_prefix` form (e.g. "my_sel@a3f1"). The hash
      prefix verifies the selection hasn't changed since you last read it. Removes
      all axioms in this axiom selection. Best-effort: skips hashes no longer in DB.
      Mutually exclusive with axiom_hashes.
    """
    if within is not None and axiom_hashes is not None:
        raise MutuallyExclusiveError(("axiom_hashes", "within"))
    if within is None and axiom_hashes is None:
        raise MissingRequiredError(("axiom_hashes", "within"))

    ont = Ontology(path)
    with session(ont) as s:
        if within is not None:
            sel_result = remove_axioms_by_selection(s, within)
            s.commit()
            entries = [("-", ha) for ha in sel_result.removed]
            summary = (
                f"Removed {len(sel_result.removed)} axioms ({sel_result.absent} already absent). "
                f"Selection {str(within.name)!r} retained."
            )
            return format_diff(entries, summary, max_rows=20)

        result = remove_axioms_by_hash(s, axiom_hashes)  # pyright: ignore[reportArgumentType]
        entries = [("-", ha) for ha in result.removed]
        s.commit()

    return format_diff(entries, f"Removed {len(result.removed)} axioms.")


tool_remove_axioms = create_tool(
    remove_axioms, name="remove_axioms", annotations=ToolAnnotations(destructiveHint=True)
)
