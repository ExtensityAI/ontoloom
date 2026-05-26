from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.axioms.deserialize import load_axiom
from ontoloom.axioms.hashing import AxiomHashPrefix, resolve_hash_prefix
from ontoloom.axioms.mutations import remove_by_hash, remove_by_selection
from ontoloom.axioms.types import HashedAxiom
from ontoloom.connection import Ontology, session
from ontoloom.models import FrozenModel, make_tag_resolver, tagged, tagged_union_meta
from ontoloom.query.constraints import InAxiomSelection
from ontoloom.query.dispatch import run
from ontoloom.query.list_axioms import ListAxioms
from ontoloom.selections.store import get_axiom_selection
from ontoloom.selections.types import AxiomSelectionName
from ontoloom.utils import dquoted

from ontoloom_mcp.components.confirmation import (
    ConfirmationRequiredError,
    confirmation_token,
)
from ontoloom_mcp.components.formatting import format_diff, format_selection_ref
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


class ByHashes(FrozenModel):
    """Target a set of axioms by hash (full or unambiguous prefix)."""

    hashes: Annotated[tuple[AxiomHashPrefix, ...], MinLen(1)]


class BySelection(FrozenModel):
    """Target every axiom in an axiom-selection."""

    name: AxiomSelectionName


_get_remove_axioms_target_tag = make_tag_resolver(
    (ByHashes, BySelection), union_name="RemoveAxiomsTarget"
)

RemoveAxiomsTarget = Annotated[
    tagged(ByHashes) | tagged(BySelection),
    *tagged_union_meta(_get_remove_axioms_target_tag),
]


def remove_axioms(path: OntologyPath, target: RemoveAxiomsTarget, confirm: str | None = None):
    """Remove axioms by hash or by axiom-selection.

    `target` is one of:
    - `{"hashes": [...]}`: Each hash (full or unambiguous prefix) must match
      exactly one axiom. Atomic: if any hash fails to resolve, nothing is removed.
      No confirmation required (hashes are content-addressed -> never stale).
    - `{"name": "axioms:NAME"}`: Removes every axiom in the axiom-selection.
      The first call previews the axioms that would be removed and raises
      `ConfirmationRequiredError` with a `confirm` token bound to the
      selection's current contents. Call again with that token to perform the
      removal. If the selection changes in between, the token no longer matches
      and a fresh preview is shown. Best-effort: skips hashes no longer in the DB.
    """
    ont = Ontology(path)
    with session(ont) as s:
        match target:
            case BySelection(name=name):
                meta = get_axiom_selection(s, name.bare)
                token = confirmation_token("remove_axioms", name.bare, meta.hash, str(meta.size))

                if confirm != token:
                    rows = run(s, ListAxioms(constraints=(InAxiomSelection(name=name),)))
                    entries = [
                        ("-", HashedAxiom(axiom=load_axiom(data), hash=h)) for h, data in rows
                    ]
                    summary = f"Removing {len(entries)} axioms in selection {dquoted(name)}."
                    raise ConfirmationRequiredError(
                        format_diff(entries, summary, max_rows=20), token
                    )

                sel_result = remove_by_selection(s, name)
                s.commit()
                entries = [("-", ha) for ha in sel_result.removed]
                summary = (
                    f"Removed {len(sel_result.removed)} axioms "
                    f"({sel_result.absent} already absent). "
                    f"Selection {format_selection_ref(sel_result.meta)} retained."
                )
                return format_diff(entries, summary, max_rows=20)

            case ByHashes(hashes=hashes):
                resolved = [resolve_hash_prefix(s, p) for p in hashes]
                result = remove_by_hash(s, resolved)
                entries = [("-", ha) for ha in result.removed]
                s.commit()
                return format_diff(entries, f"Removed {len(result.removed)} axioms.")

            case _:
                msg = f"unhandled RemoveAxiomsTarget variant: {type(target).__name__}"
                raise ValueError(msg)


tool_remove_axioms = create_tool(
    remove_axioms, name="remove_axioms", annotations=ToolAnnotations(destructiveHint=True)
)
