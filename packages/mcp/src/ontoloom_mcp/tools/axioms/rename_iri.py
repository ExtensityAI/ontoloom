from mcp.types import ToolAnnotations
from ontoloom.axioms.mutations import rename_iri as core_rename_iri
from ontoloom.connection import Ontology, session
from ontoloom.owl.iri import IRI
from ontoloom.selections.store import upsert_axiom_selection
from ontoloom.selections.types import AxiomSelectionName, WriteMode

from ontoloom_mcp.components.confirmation import (
    ConfirmationRequiredError,
    confirmation_token,
)
from ontoloom_mcp.components.locking import (
    LockedAxiomSelectionName,
    format_locked_quoted,
    verify_lock,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def rename_iri(
    path: OntologyPath,
    old_iri: IRI,
    new_iri: IRI,
    within: LockedAxiomSelectionName | None = None,
    into: AxiomSelectionName | None = None,
    mode: WriteMode = WriteMode.CREATE,
    confirm: str | None = None,
):
    """Rename an IRI across all (or restricted) axioms.

    Finds every axiom mentioning `old_iri`, replaces it with `new_iri`. No-op
    if `old_iri` is not in use.

    Args:
    - `old_iri`: IRI to replace.
    - `new_iri`: New IRI to use in its place.
    - `within`: Optional locked axiom selection reference
      `"axioms:NAME@hash_prefix"` (e.g. `"axioms:my_sel@a3f1b2c4"`). The hash
      prefix verifies the selection hasn't changed since you last observed it.
    - `into`: Optional axiom selection (e.g. `"axioms:renamed"`) to populate
      with the post-rename hashes of every replaced axiom. Use to inspect or
      further operate on the affected axioms without re-querying.
    - `mode`: `create` (default) refuses if the selection name already exists; `replace` overwrites it.
    - `confirm`: When the rename would merge axioms into existing ones (hash
      collision => annotations on the merged axioms may be lost), the first
      call raises `ConfirmationRequiredError` with a token. Pass that token
      here to apply the change.
    """
    ont = Ontology(path)
    with session(ont) as s:
        verified = verify_lock(s, within) if within is not None else None
        result = core_rename_iri(s, old_iri, new_iri, within=verified)

        if result.colliding_hashes:
            token = confirmation_token(
                "rename_iri", str(old_iri), str(new_iri), *sorted(result.colliding_hashes)
            )
            if confirm != token:
                msg = (
                    f"Renaming {old_iri} -> {new_iri} would merge "
                    f"{len(result.colliding_hashes)} axiom(s) into existing axioms "
                    f"(annotations on the merged axioms may be lost). "
                    f"Colliding new hashes: {sorted(result.colliding_hashes)}."
                )
                raise ConfirmationRequiredError(msg, token)

        upserted = None
        if into is not None:
            new_hashes = [r.new.hash for r in result.replaced if not r.was_noop]
            upserted = upsert_axiom_selection(
                s,
                into.bare,
                new_hashes,
                f"rename_iri({old_iri} -> {new_iri})",
                mode=mode,
            )

        s.commit()

    if not result.replaced:
        return f"No axioms found mentioning {old_iri}. No-op."

    actual = [r for r in result.replaced if not r.was_noop]
    merged = [r for r in actual if r.was_merged_into_existing]
    parts = [f"Renamed {old_iri} -> {new_iri}: {len(actual)} axioms replaced."]
    if merged:
        parts.append(f"{len(merged)} merged into existing axioms.")
    if upserted is not None:
        sel = upserted.selection
        parts.append(f"Saved to {format_locked_quoted(sel)} ({sel.size} items).")
    return " ".join(parts)


tool_rename_iri = create_tool(
    rename_iri,
    name="rename_iri",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True),
)
