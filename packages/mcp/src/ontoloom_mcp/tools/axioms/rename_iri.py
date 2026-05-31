from mcp.types import ToolAnnotations
from ontoloom.axioms.hashing import short_hash
from ontoloom.axioms.mutations import rename_iri as core_rename_iri
from ontoloom.axioms.types import HashedAxiom
from ontoloom.connection import Ontology, session
from ontoloom.owl.iri import IRI
from ontoloom.selections.store import get_axiom_selection, upsert_axiom_selection
from ontoloom.selections.types import SelectionName, WriteMode

from ontoloom_mcp.components.confirmation import (
    ConfirmationRequiredError,
    confirmation_token,
)
from ontoloom_mcp.components.formatting import (
    RenameSource,
    format_diff,
    format_saved_line,
    format_source,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath

DIFF_MAX_ROWS = 20


def rename_iri(
    path: OntologyPath,
    old_iri: IRI,
    new_iri: IRI,
    within: SelectionName | None = None,
    into: SelectionName | None = None,
    mode: WriteMode = WriteMode.CREATE,
    confirm: str | None = None,
):
    """Rename an IRI across all (or restricted) axioms.

    Finds every axiom mentioning `old_iri`, replaces it with `new_iri`. No-op
    if `old_iri` is not in use.

    Args:
    - `old_iri`: IRI to replace.
    - `new_iri`: New IRI to use in its place.
    - `within`: Optional axiom selection (e.g. `"my_sel"`) restricting
      the rename to axioms in that scope. Scope staleness is only re-checked
      when the rename hits a collision (it is folded into the confirm token).
    - `into`: Optional axiom selection (e.g. `"renamed"`) to populate
      with the post-rename hashes of every replaced axiom. Use to inspect or
      further operate on the affected axioms without re-querying.
    - `mode`: `create` (default) refuses if the selection name already exists; `replace` overwrites it.
    - `confirm`: When the rename would merge axioms into existing ones (hash
      collision => annotations on the merged axioms may be lost), the first
      call raises `ConfirmationRequiredError` with a token. Pass that token
      here to apply the change.
    """
    source = format_source(RenameSource(str(old_iri), str(new_iri), within=within))

    ont = Ontology(path)
    with session(ont) as s:
        result = core_rename_iri(s, old_iri, new_iri, within=within)

        if result.colliding_hashes:
            parts = ["rename_iri", str(old_iri), str(new_iri), *sorted(result.colliding_hashes)]
            if within is not None:
                parts += [str(within), get_axiom_selection(s, within).hash]

            token = confirmation_token(*parts)
            if confirm != token:
                short_hashes = ", ".join(
                    f"[{short_hash(h)}]" for h in sorted(result.colliding_hashes)
                )
                msg = (
                    f"Renaming {old_iri} -> {new_iri} would merge "
                    f"{len(result.colliding_hashes)} axiom(s) into existing axioms "
                    f"(annotations on the merged axioms may be lost). "
                    f"Colliding new hashes: {short_hashes}."
                )
                raise ConfirmationRequiredError(msg, token)

        upserted = None
        if into is not None:
            new_hashes = [r.new.hash for r in result.replaced if not r.was_noop]
            upserted = upsert_axiom_selection(s, into, new_hashes, source, mode=mode)

        s.commit()

    if not result.replaced:
        return f"No axioms found mentioning {old_iri}. No-op."

    actual = [r for r in result.replaced if not r.was_noop]
    merged = [r for r in actual if r.was_merged_into_existing]

    summary = f"Renamed {old_iri} -> {new_iri}: {len(actual)} axioms replaced."
    if merged:
        summary += f" {len(merged)} merged into existing axioms."

    entries: list[tuple[str, HashedAxiom]] = []
    for r in actual:
        entries.append(("-", r.old))
        entries.append(("+", r.new))

    body = format_diff(entries, summary=summary, max_rows=DIFF_MAX_ROWS)

    if upserted is not None:
        body += "\n\n" + format_saved_line(upserted)

    return body


tool_rename_iri = create_tool(
    rename_iri,
    name="rename_iri",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True),
)
