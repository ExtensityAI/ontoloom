from mcp.types import ToolAnnotations
from ontoloom.axioms.mutations import rename_iri as core_rename_iri
from ontoloom.connection import Ontology, session
from ontoloom.owl.iri import IRI
from ontoloom.selections.store import get_axiom_selection, upsert_axiom_selection
from ontoloom.selections.types import AxiomSelectionName, WriteMode

from ontoloom_mcp.components.confirmation import (
    ConfirmationRequiredError,
    confirmation_token,
)
from ontoloom_mcp.components.formatting import format_selection_ref
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def rename_iri(
    path: OntologyPath,
    old_iri: IRI,
    new_iri: IRI,
    within: AxiomSelectionName | None = None,
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
    - `within`: Optional axiom selection (e.g. `"axioms:my_sel"`) restricting
      the rename to axioms in that scope. Scope staleness is only re-checked
      when the rename hits a collision (it is folded into the confirm token).
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
        result = core_rename_iri(s, old_iri, new_iri, within=within)

        if result.colliding_hashes:
            parts = ["rename_iri", str(old_iri), str(new_iri), *sorted(result.colliding_hashes)]
            if within is not None:
                parts += [str(within), get_axiom_selection(s, within.bare).hash]

            token = confirmation_token(*parts)
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
        parts.append(f"Saved to {format_selection_ref(sel)} ({sel.size} items).")
    return " ".join(parts)


tool_rename_iri = create_tool(
    rename_iri,
    name="rename_iri",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True),
)
