from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.axioms.store import remove_by_hash, remove_by_selection, resolve_hash_prefix
from ontoloom.connection import Ontology, session
from ontoloom.hashing import AxiomHashPrefix
from ontoloom.models import FrozenModel, make_tag_resolver, tagged, tagged_union_meta
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.locking import LockedAxiomSelectionName, format_locked, verify_lock
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


class ByHashes(FrozenModel):
    """Target a set of axioms by hash (full or unambiguous prefix)."""

    hashes: Annotated[tuple[AxiomHashPrefix, ...], MinLen(1)]


class BySelection(FrozenModel):
    """Target every axiom in a locked axiom-selection."""

    selection: LockedAxiomSelectionName


_get_remove_axioms_target_tag = make_tag_resolver(
    (ByHashes, BySelection), union_name="RemoveAxiomsTarget"
)

RemoveAxiomsTarget = Annotated[
    tagged(ByHashes) | tagged(BySelection),
    *tagged_union_meta(_get_remove_axioms_target_tag),
]


def remove_axioms(path: OntologyPath, target: RemoveAxiomsTarget):
    """Remove axioms by hash or by locked axiom-selection.

    `target` is one of:
    - `{"hashes": [...]}`: Each hash (full or unambiguous prefix) must match
      exactly one axiom. Atomic: if any hash fails to resolve, nothing is removed.
    - `{"selection": "axioms:NAME@hash_prefix"}`: Removes every axiom in the locked
      axiom-selection. The hash prefix verifies the selection hasn't changed
      since you last read it. Best-effort: skips hashes no longer in the DB.
    """
    ont = Ontology(path)
    with session(ont) as s:
        match target:
            case BySelection(selection=locked):
                verified = verify_lock(s, locked)
                sel_result = remove_by_selection(s, verified)
                s.commit()
                entries = [("-", ha) for ha in sel_result.removed]
                summary = (
                    f"Removed {len(sel_result.removed)} axioms "
                    f"({sel_result.absent} already absent). "
                    f"Selection {dquoted(format_locked(sel_result.meta))} retained."
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
