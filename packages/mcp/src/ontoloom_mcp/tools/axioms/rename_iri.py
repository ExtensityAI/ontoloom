from mcp.types import ToolAnnotations
from ontoloom.axioms.store import rename_iri as core_rename_iri
from ontoloom.connection import Ontology
from ontoloom.owl.iri import IRI
from ontoloom.selections.types import LockedSelection
from ontoloom.transactions import atomic, dry_run

from ontoloom_mcp.components.confirmation import (
    ConfirmationRequiredError,
    confirmation_token,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def rename_iri(
    path: OntologyPath,
    old_iri: IRI,
    new_iri: IRI,
    within: LockedSelection | None = None,
    confirm: str | None = None,
):
    """Rename an IRI across all (or restricted) axioms.

    Finds every axiom mentioning `old_iri`, replaces it with `new_iri`, and
    saves each as an atomic replace event. All events share one batch_id for
    atomic revert. No-op if `old_iri` is not in use.

    Args:
    - `old_iri`: IRI to replace.
    - `new_iri`: New IRI to use in its place.
    - `within`: Optional `name@hash_prefix` reference (e.g. "my_sel@a3f1") to
      restrict the rename to an axiom selection. The hash prefix verifies the
      selection hasn't changed since you last observed it.
    - `confirm`: When the rename would merge axioms into existing ones (hash
      collision => annotations on the merged axioms may be lost), the first
      call raises `ConfirmationRequiredError` with a token. Pass that token
      here to apply the change.
    """
    ont = Ontology(path)
    with dry_run(ont) as s:
        preview = core_rename_iri(s, old_iri, new_iri, within=within)

    if preview.colliding_hashes:
        token = confirmation_token(
            "rename_iri", str(old_iri), str(new_iri), *sorted(preview.colliding_hashes)
        )
        if confirm != token:
            msg = (
                f"Renaming {old_iri} -> {new_iri} would merge "
                f"{len(preview.colliding_hashes)} axiom(s) into existing axioms "
                f"(annotations on the merged axioms may be lost). "
                f"Colliding new hashes: {sorted(preview.colliding_hashes)}."
            )
            raise ConfirmationRequiredError(msg, token)

    with atomic(ont) as s:
        result = core_rename_iri(s, old_iri, new_iri, within=within)

    if not result.replaced:
        return f"No axioms found mentioning {old_iri}. No-op."

    actual = [r for r in result.replaced if not r.was_noop]
    merged = [r for r in actual if r.was_merged_into_existing]
    parts = [f"Renamed {old_iri} -> {new_iri}: {len(actual)} axioms replaced."]
    if merged:
        parts.append(f"{len(merged)} merged into existing axioms.")
    parts.append(f"Batch: {result.batch_id}")
    return " ".join(parts)


tool_rename_iri = create_tool(
    rename_iri,
    name="rename_iri",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True),
)
