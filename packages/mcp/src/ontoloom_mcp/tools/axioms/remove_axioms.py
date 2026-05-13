from mcp.types import ToolAnnotations
from ontoloom.axioms.store import remove_by_hash, remove_by_selection, resolve_hash_prefix
from ontoloom.axioms.types import ByHashes, BySelection, RemoveAxiomsTarget
from ontoloom.connection import Ontology, session
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def remove_axioms(path: OntologyPath, target: RemoveAxiomsTarget):
    """Remove axioms by hash or by locked axiom-selection.

    `target` is one of:
    - `{"hashes": [...]}`: Each hash (full or unambiguous prefix) must match
      exactly one axiom. Atomic: if any hash fails to resolve, nothing is removed.
    - `{"selection": "name@hash_prefix"}`: Removes every axiom in the locked
      axiom-selection. The hash prefix verifies the selection hasn't changed
      since you last read it. Best-effort: skips hashes no longer in the DB.
    """
    ont = Ontology(path)
    with session(ont) as s:
        match target:
            case BySelection(selection=within):
                sel_result = remove_by_selection(s, within)
                s.commit()
                entries = [("-", ha) for ha in sel_result.removed]
                summary = (
                    f"Removed {len(sel_result.removed)} axioms "
                    f"({sel_result.absent} already absent). "
                    f"Selection {dquoted(within.name)} retained."
                )
                return format_diff(entries, summary, max_rows=20)

            case ByHashes(hashes=hashes):
                resolved = [resolve_hash_prefix(s, p) for p in hashes]
                result = remove_by_hash(s, resolved)
                entries = [("-", ha) for ha in result.removed]
                s.commit()
                return format_diff(entries, f"Removed {len(result.removed)} axioms.")


tool_remove_axioms = create_tool(
    remove_axioms, name="remove_axioms", annotations=ToolAnnotations(destructiveHint=True)
)
