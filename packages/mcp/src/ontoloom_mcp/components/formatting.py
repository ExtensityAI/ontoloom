from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from ontoloom.axioms.entity_walker import iter_axiom_entities
from ontoloom.axioms.hashing import short_hash
from ontoloom.axioms.types import HashedAxiom
from ontoloom.connection import Session
from ontoloom.entities.reader import lookup_entity_labels
from ontoloom.owl.axioms import BaseAxiom
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.selections.store import AxiomUpsertResult, EntityUpsertResult
from ontoloom.selections.types import AxiomSelection, EntitySelection
from ontoloom.utils import dquoted

SELECT_PREVIEW = 5
SELECT_INLINE_MAX = 20


@dataclass(frozen=True, slots=True)
class Ref:
    """An IRI paired with its rdfs:label (if any) for display."""

    iri: IRI
    label: str | None


def unique_iris_in(axiom: BaseAxiom) -> list[IRI]:
    """Ordered unique IRIs referenced by an axiom (single walk, dedup preserved)."""
    seen: set[IRI] = set()
    out: list[IRI] = []
    for iri, _, _ in iter_axiom_entities(axiom):
        if iri not in seen:
            seen.add(iri)
            out.append(iri)
    return out


def unique_iris_across(axioms: Sequence[HashedAxiom]) -> list[IRI]:
    """Extract unique entity IRIs from a list of hashed axioms (insertion-ordered)."""
    seen: set[IRI] = set()
    out: list[IRI] = []
    for ha in axioms:
        for iri in unique_iris_in(ha.axiom):
            if iri not in seen:
                seen.add(iri)
                out.append(iri)
    return out


def build_refs(s: Session, iris: Sequence[IRI]) -> list[Ref]:
    """Look up rdfs:labels for `iris` and pair each with its label."""
    labels = lookup_entity_labels(s, list(iris))
    return [Ref(iri=iri, label=labels.get(iri)) for iri in iris]


def build_refs_per_axiom(s: Session, axioms: Sequence[HashedAxiom]) -> list[list[Ref]]:
    """Build per-axiom Ref lists, sharing one label lookup across all axioms."""
    all_iris = unique_iris_across(axioms)
    labels = lookup_entity_labels(s, list(all_iris))
    return [
        [Ref(iri=iri, label=labels.get(iri)) for iri in unique_iris_in(ha.axiom)] for ha in axioms
    ]


def format_selection_ref(meta: AxiomSelection | EntitySelection) -> str:
    kind = "axioms" if isinstance(meta, AxiomSelection) else "entities"
    return dquoted(f"{kind}:{meta.name}")


def format_ref(ref: Ref) -> str:
    """Render an IRI with its label as `iri "label"`, or just the IRI if no label."""
    return f"{ref.iri} {dquoted(ref.label)}" if ref.label else str(ref.iri)


def format_roles(roles: AbstractSet[EntityType]):
    return ", ".join(sorted(str(r) for r in roles)) or "none"


def format_axiom_annotations(axiom: BaseAxiom):
    """Indented Turtle-style `# prop value` lines for an axiom's metadata annotations.

    Returns an empty list when the axiom carries no annotations. Callers
    join with newlines to attach the block under the axiom's primary line.
    Turtle-style (whitespace separator, no second colon) avoids visual
    collision with the prefix's `:` in IRIs.
    """
    return [f"  # {ann.property} {ann.value}" for ann in axiom.annotations]


def _format_axiom_line(ha: HashedAxiom, refs: Sequence[Ref] = ()):
    """Format a single axiom block: head line + any annotation continuation lines."""
    head = f"[{short_hash(ha.hash)}] {ha.axiom}"
    hints = [format_ref(r) for r in refs if r.label]

    if hints:
        head += "  # " + ", ".join(hints)
    annotation_lines = format_axiom_annotations(ha.axiom)

    if annotation_lines:
        return head + "\n" + "\n".join(annotation_lines)
    return head


def format_diff(
    entries: Sequence[tuple[str, HashedAxiom]],
    summary: str,
    refs_per_entry: Sequence[Sequence[Ref]] = (),
    max_rows: int | None = None,
):
    capped = entries if max_rows is None else entries[:max_rows]
    refs_list: Sequence[Sequence[Ref]] = (
        refs_per_entry[: len(capped)] if refs_per_entry else [()] * len(capped)
    )
    lines = [
        f"{tag} {_format_axiom_line(ha, refs)}"
        for (tag, ha), refs in zip(capped, refs_list, strict=True)
    ]
    if max_rows is not None and len(entries) > max_rows:
        lines.append(f"... and {len(entries) - max_rows} more")
    changes = "\n".join(lines)
    return f"{summary}\n\n```diff\n{changes}\n```"


def format_axiom_listing(
    axioms: Sequence[HashedAxiom],
    refs_per_axiom: Sequence[Sequence[Ref]] = (),
):
    if not axioms:
        return ""
    refs_list: Sequence[Sequence[Ref]] = refs_per_axiom or [()] * len(axioms)
    return "\n".join(
        _format_axiom_line(ha, refs) for ha, refs in zip(axioms, refs_list, strict=True)
    )


def format_selection_result(
    upserted: AxiomUpsertResult | EntityUpsertResult,
    page_text: str,
):
    sel = upserted.selection
    kind_label = "axioms" if isinstance(upserted, AxiomUpsertResult) else "entities"
    parts = [f"{sel.size} {kind_label} -> {format_selection_ref(sel)}."]
    if upserted.previous_size is not None:
        parts.append(f"Overwrote previous ({upserted.previous_size} items).")

    if sel.size <= SELECT_INLINE_MAX:
        parts.append("")
        parts.append(page_text)
    else:
        parts.append(f"Preview (first {SELECT_PREVIEW}):")
        parts.append("")
        parts.append(page_text)
        parts.append(
            f"\nUse `read_selection` with name {dquoted(sel.name)} to browse all {sel.size} results."
        )

    return "\n".join(parts)
