from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from typing import Literal

from ontoloom.axioms.entity_walker import iter_axiom_entities
from ontoloom.axioms.hashing import AxiomHash, short_hash
from ontoloom.axioms.types import HashedAxiom
from ontoloom.connection import Session
from ontoloom.entities.reader import lookup_entity_labels
from ontoloom.owl.axioms import BaseAxiom
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.selections.store import AxiomUpsertResult, EntityUpsertResult
from ontoloom.selections.types import (
    AxiomSelection,
    EntitySelection,
    SelectionKind,
    SelectionName,
)
from ontoloom.utils import dquoted

SELECT_PREVIEW = 5
SELECT_INLINE_MAX = 20

_KIND_NOUN: dict[SelectionKind, tuple[str, str]] = {
    SelectionKind.AXIOMS: ("axiom", "axioms"),
    SelectionKind.ENTITIES: ("entity", "entities"),
}


def format_kinded_count(kind: SelectionKind, n: int):
    """Render `n <noun>`, pluralizing the kind's noun unless `n == 1`.

    The sole place a selection kind surfaces as a noun.
    """
    singular, plural = _KIND_NOUN[kind]
    return f"{n} {singular if n == 1 else plural}"


def format_drift(present: int, missing: int):
    """Render `<present> present, <missing> missing`, or `""` when nothing is missing."""
    if missing == 0:
        return ""

    return f"{present} present, {missing} missing"


def _kind_of(meta: AxiomSelection | EntitySelection) -> SelectionKind:
    return SelectionKind.AXIOMS if isinstance(meta, AxiomSelection) else SelectionKind.ENTITIES


def format_pagination(
    x: int,
    y: int,
    z: int,
    kind: SelectionKind,
    *,
    filter: str | None = None,  # noqa: A002
):
    """Render a paginated header: either an empty-page sentence or a `Showing X-Y of Z <noun>:` line.

    Empty form when `z == 0` or `x > y`; range form otherwise. Filter, when
    given, surfaces as a parenthesized `(filter: <value>)` tail before the
    terminator (period for empty, colon for range).
    """
    filter_tail = f" (filter: {filter})" if filter is not None else ""

    if z == 0 or x > y:
        return f"{format_kinded_count(kind, 0)}{filter_tail}."

    return f"Showing {x}-{y} of {format_kinded_count(kind, z)}{filter_tail}:"


def format_read_header(meta: AxiomSelection | EntitySelection, present: int, missing: int):
    """Noun-led header for a read response; drift is shown unconditionally.

    Total count is `present + missing` (so singular/plural follows the total,
    not the selection's stored size). Unlike `format_drift`, the drift tail
    appears even when `missing == 0`.
    """
    kind = _kind_of(meta)
    total = present + missing
    return (
        f"{dquoted(meta.name)}: {format_kinded_count(kind, total)} "
        f"- {present} present, {missing} missing"
    )


def format_list_row(
    meta: AxiomSelection | EntitySelection, present: int, missing: int, source: str
):
    """Indented per-selection row: `  "name": N <noun>[, M missing] - source: <source>`.

    Drift appears as a comma-tail inside the noun phrase only when `missing > 0`.
    """
    kind = _kind_of(meta)
    total = present + missing
    drift_tail = f", {missing} missing" if missing > 0 else ""
    return (
        f"  {dquoted(meta.name)}: {format_kinded_count(kind, total)}{drift_tail} - source: {source}"
    )


def format_within_scope(meta: AxiomSelection | EntitySelection):
    """Render a `Within "name" (N <noun>)` scope fragment from already-resolved meta.

    No trailing colon; callers append one if they're using it as a header.
    """
    kind = _kind_of(meta)
    return f"Within {dquoted(meta.name)} ({format_kinded_count(kind, meta.size)})"


def format_overwrite_note(previous_size: int | None):
    """A leading-space sentence noting an overwrite, or `""` when nothing was replaced.

    The leading space lets callers concatenate directly onto a prior sentence.
    """
    if previous_size is None:
        return ""

    return f" Replaced previous ({previous_size} items)."


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


def format_entity_line(ref: Ref, roles: frozenset[EntityType]):
    """Canonical one-line entity row: `iri[ (roles)][ "label"]`.

    Roles render as a sorted, comma-joined enum-value list inside parens;
    the parens are omitted entirely when `roles` is empty. The label, when
    present, is double-quoted and trails the roles.
    """
    parts = [str(ref.iri)]
    if roles:
        parts.append(f"({', '.join(sorted(str(r) for r in roles))})")
    if ref.label:
        parts.append(dquoted(ref.label))
    return " ".join(parts)


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


def format_missing_axiom_line(h: AxiomHash):
    """Render the head line for a selection item whose axiom is no longer present."""
    return f"[{short_hash(h)}] *missing*"


def format_diff(
    entries: Sequence[tuple[str, HashedAxiom]],
    summary: str,
    max_rows: int | None = None,
):
    capped = entries if max_rows is None else entries[:max_rows]
    refs_list: Sequence[Sequence[Ref]] = [()] * len(capped)
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


@dataclass(frozen=True, slots=True)
class ToolFilterSource:
    """Source for a tool invocation: tool name plus its non-default filter args.

    Filters are stored as `tuple[tuple[str, object], ...]` so the descriptor
    stays hashable under `frozen=True`; the constructor accepts any Mapping
    and preserves insertion order.
    """

    kind: Literal["tool"] = field(init=False, default="tool")
    tool: str
    filters: tuple[tuple[str, object], ...]
    within: SelectionName | str | None = None

    def __init__(
        self,
        tool: str,
        filters: Mapping[str, object],
        within: SelectionName | str | None = None,
    ):
        object.__setattr__(self, "tool", tool)
        object.__setattr__(self, "filters", tuple(filters.items()))
        object.__setattr__(self, "within", within)


@dataclass(frozen=True, slots=True)
class RenameSource:
    """Source for a `rename_iri` invocation."""

    kind: Literal["rename"] = field(init=False, default="rename")
    old: str
    new: str
    within: SelectionName | str | None = None


@dataclass(frozen=True, slots=True)
class SetExprSource:
    """Source for a `create_selection` invocation; `expr` is the rendered set-expression."""

    kind: Literal["set_expr"] = field(init=False, default="set_expr")
    expr: str
    within: SelectionName | str | None = None


type SourceDescriptor = ToolFilterSource | RenameSource | SetExprSource


def _format_filter_value(v: object) -> str:
    # Per-filter value formatting is intentionally type-discriminated so quoted
    # strings, bare bools/ints, and bracketed string lists all render naturally.
    # `repr` is the safe fallback for anything else.
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return dquoted(v)
    if isinstance(v, list):
        return "[" + ", ".join(dquoted(item) for item in v) + "]"
    return repr(v)


def format_source(src: SourceDescriptor) -> str:
    """Render a source descriptor to its breadcrumb string.

    A uniform ` within "<name>"` suffix is appended when `src.within` is set.
    """
    match src:
        case ToolFilterSource():
            if src.filters:
                args = ", ".join(f"{k}={_format_filter_value(v)}" for k, v in src.filters)
                body = f"{src.tool}({args})"
            else:
                body = src.tool
        case RenameSource():
            body = f"rename_iri({src.old} -> {src.new})"
        case SetExprSource():
            body = src.expr
        case _:
            msg = f"Unknown source descriptor: {type(src).__name__}"
            raise ValueError(msg)

    if src.within is None:
        return body
    return f"{body} within {dquoted(str(src.within))}"


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
