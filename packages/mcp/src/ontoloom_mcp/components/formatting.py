from collections.abc import Sequence
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
from ontoloom.prefixes.types import PrefixName
from ontoloom.query.dispatch import execute
from ontoloom.selections.expr import SetExpr
from ontoloom.selections.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.read_entity_selection import ReadEntitySelection
from ontoloom.selections.store import AxiomUpsertResult, EntityUpsertResult
from ontoloom.selections.types import (
    AxiomSelection,
    EntitySelection,
    SelectionKind,
    SelectionName,
    ShowFilter,
)
from ontoloom.utils import dquoted

PREVIEW_ROWS = 10

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


def format_axiom_blocks(
    axioms: Sequence[HashedAxiom],
    refs_per_axiom: Sequence[Sequence[Ref]] = (),
) -> list[str]:
    """Render one block per axiom.

    Each entry is the complete block for one axiom (head line plus any
    annotation continuation lines joined as a single multi-line string),
    so callers can interleave with other rows without splitting heads from
    their continuations.
    """
    if not axioms:
        return []
    refs_list: Sequence[Sequence[Ref]] = refs_per_axiom or [()] * len(axioms)
    return [_format_axiom_line(ha, refs) for ha, refs in zip(axioms, refs_list, strict=True)]


def format_axiom_listing(
    axioms: Sequence[HashedAxiom],
    refs_per_axiom: Sequence[Sequence[Ref]] = (),
):
    return "\n".join(format_axiom_blocks(axioms, refs_per_axiom))


@dataclass(frozen=True, slots=True)
class SearchAxiomsSource:
    """Source for a `search_axioms` invocation."""

    kind: Literal["search_axioms"] = field(init=False, default="search_axioms")
    query: str | None
    properties: tuple[IRI, ...]
    within: SelectionName | None


@dataclass(frozen=True, slots=True)
class SearchEntitiesSource:
    """Source for a `search_entities` invocation.

    `exclude_deprecated` is carried so non-default values surface in the
    breadcrumb; the default (`True`) is omitted.
    """

    kind: Literal["search_entities"] = field(init=False, default="search_entities")
    query: str | None
    role: EntityType | None
    namespace: PrefixName | None
    declared: bool | None
    properties: tuple[IRI, ...]
    exclude_deprecated: bool
    within: SelectionName | None


@dataclass(frozen=True, slots=True)
class MatchAxiomsSource:
    """Source for a `match_axioms` invocation.

    The structural pattern is intentionally omitted - no compact textual
    rendering is meaningful, so only the `within` scope surfaces.
    """

    kind: Literal["match_axioms"] = field(init=False, default="match_axioms")
    within: SelectionName | None


@dataclass(frozen=True, slots=True)
class GetEntitySource:
    """Source for a `get_entity` invocation that populates an axiom selection."""

    kind: Literal["get_entity"] = field(init=False, default="get_entity")
    iri: IRI
    within: SelectionName | None


@dataclass(frozen=True, slots=True)
class FindDuplicatesSource:
    """Source for a `find_duplicate_entities` invocation."""

    kind: Literal["find_duplicate_entities"] = field(init=False, default="find_duplicate_entities")
    annotation_property: IRI
    within: SelectionName | None


@dataclass(frozen=True, slots=True)
class RenameSource:
    """Source for a `rename_iri` invocation."""

    kind: Literal["rename_iri"] = field(init=False, default="rename_iri")
    old: IRI
    new: IRI
    within: SelectionName | None


@dataclass(frozen=True, slots=True)
class SetExprSource:
    """Source for a `create_selection` invocation; renders via `str(expr)`."""

    kind: Literal["set_expr"] = field(init=False, default="set_expr")
    expr: SetExpr


type StorageSource = (
    SearchAxiomsSource
    | SearchEntitiesSource
    | MatchAxiomsSource
    | GetEntitySource
    | FindDuplicatesSource
    | RenameSource
    | SetExprSource
)

type WriteBlockSource = (
    SearchAxiomsSource
    | SearchEntitiesSource
    | MatchAxiomsSource
    | FindDuplicatesSource
    | SetExprSource
)


def _within_suffix(within: SelectionName | None) -> str:
    if within is None:
        return ""
    return f" within {dquoted(within)}"


def _properties_arg(properties: tuple[IRI, ...]) -> str:
    return "[" + ", ".join(dquoted(p) for p in properties) + "]"


def format_source(src: StorageSource) -> str:  # noqa: C901
    """Render a source descriptor to its breadcrumb string.

    A uniform ` within "<name>"` suffix is appended when `src.within` is set
    (variants that have a `within` field). `SetExprSource` defers to
    `str(expr)` and carries no separate within.
    """
    match src:
        case SearchAxiomsSource():
            args: list[str] = []
            if src.query is not None:
                args.append(f"query={dquoted(src.query)}")
            if src.properties:
                args.append(f"properties={_properties_arg(src.properties)}")
            body = f"search_axioms({', '.join(args)})" if args else "search_axioms"
            return f"{body}{_within_suffix(src.within)}"
        case SearchEntitiesSource():
            ents_args: list[str] = []
            if src.query is not None:
                ents_args.append(f"query={dquoted(src.query)}")
            if src.role is not None:
                ents_args.append(f"role={dquoted(src.role)}")
            if src.namespace is not None:
                ents_args.append(f"namespace={dquoted(src.namespace)}")
            if src.declared is not None:
                ents_args.append(f"declared={src.declared}")
            if src.properties:
                ents_args.append(f"properties={_properties_arg(src.properties)}")
            if not src.exclude_deprecated:
                ents_args.append(f"exclude_deprecated={src.exclude_deprecated}")
            body = f"search_entities({', '.join(ents_args)})" if ents_args else "search_entities"
            return f"{body}{_within_suffix(src.within)}"
        case MatchAxiomsSource():
            return f"match_axioms{_within_suffix(src.within)}"
        case GetEntitySource():
            return f"get_entity(iri={dquoted(src.iri)}){_within_suffix(src.within)}"
        case FindDuplicatesSource():
            return (
                f"find_duplicate_entities(annotation_property={dquoted(src.annotation_property)})"
                f"{_within_suffix(src.within)}"
            )
        case RenameSource():
            return f"rename_iri({src.old} -> {src.new}){_within_suffix(src.within)}"
        case SetExprSource():
            return str(src.expr)
        case _:
            msg = f"Unknown source descriptor: {type(src).__name__}"
            raise ValueError(msg)


def _empty_message(src: WriteBlockSource) -> str:
    """Compose the trailing sentence for the empty-selection case, per source kind."""
    rendered = format_source(src)
    match src:
        case SearchAxiomsSource():
            return f"No matches for {rendered}."
        case SearchEntitiesSource():
            return f"No entities found ({rendered})."
        case MatchAxiomsSource():
            return f"No matches for {rendered}."
        case FindDuplicatesSource():
            return f"No duplicates for {rendered}."
        case SetExprSource():
            return ""
        case _:
            msg = f"Unknown write-block source: {type(src).__name__}"
            raise ValueError(msg)


def format_saved_line(
    upserted: AxiomUpsertResult | EntityUpsertResult,
    *,
    truncated_limit: int | None = None,
):
    """Render the one-line summary for a just-upserted selection.

    Form: `Saved N <noun> to "<name>"[ (truncated...)].[ Replaced previous (M items).]`
    """
    sel = upserted.selection
    kind = _kind_of(sel)
    count = format_kinded_count(kind, sel.size)
    trunc_tail = (
        f" (truncated at limit={truncated_limit}; raise it to see more)"
        if truncated_limit is not None
        else ""
    )
    overwrite_tail = format_overwrite_note(upserted.previous_size)
    return f"Saved {count} to {dquoted(sel.name)}{trunc_tail}.{overwrite_tail}"


@dataclass(frozen=True, slots=True)
class AxiomPreviewData:
    """Pre-fetched preview rows for an axiom selection.

    Each row pairs a hashed axiom with the label refs for the entities it
    mentions, so rendering does not need a session.
    """

    kind: Literal["axioms"] = field(init=False, default="axioms")
    rows: tuple[tuple[HashedAxiom, tuple[Ref, ...]], ...]


@dataclass(frozen=True, slots=True)
class EntityPreviewData:
    """Pre-fetched preview rows for an entity selection.

    Each row pairs a Ref (iri + label) with the entity's roles.
    """

    kind: Literal["entities"] = field(init=False, default="entities")
    rows: tuple[tuple[Ref, frozenset[EntityType]], ...]


type SelectionPreviewData = AxiomPreviewData | EntityPreviewData


def fetch_preview_data(
    s: Session,
    upserted: AxiomUpsertResult | EntityUpsertResult,
) -> SelectionPreviewData:
    """Fetch the first PREVIEW_ROWS rows of a just-upserted selection for rendering.

    Dispatches by selection kind and returns a discriminated-union of pre-paired
    rows (axioms with refs, or entity refs with roles). Render with
    `format_selection_write`.
    """
    if isinstance(upserted, AxiomUpsertResult):
        page = execute(
            s,
            ReadAxiomSelection(
                selection=upserted.selection.name,
                limit=PREVIEW_ROWS,
                offset=0,
                show=ShowFilter.ALL,
            ),
        )
        page_axioms = [
            HashedAxiom(axiom=item.axiom, hash=item.hash)
            for item in page.items
            if item.axiom is not None
        ]
        refs_per_axiom = build_refs_per_axiom(s, page_axioms)
        rows = tuple(
            (ha, tuple(refs)) for ha, refs in zip(page_axioms, refs_per_axiom, strict=True)
        )
        return AxiomPreviewData(rows=rows)

    page = execute(
        s,
        ReadEntitySelection(
            selection=upserted.selection.name,
            limit=PREVIEW_ROWS,
            offset=0,
            show=ShowFilter.ALL,
        ),
    )
    entity_rows = tuple(
        (Ref(iri=item.iri, label=item.label), item.roles) for item in page.items if item.present
    )
    return EntityPreviewData(rows=entity_rows)


def _render_preview_body(preview: SelectionPreviewData) -> str:
    match preview:
        case AxiomPreviewData():
            return "\n".join(_format_axiom_line(ha, refs) for ha, refs in preview.rows)
        case EntityPreviewData():
            return "\n".join(format_entity_line(ref, roles) for ref, roles in preview.rows)
        case _:
            msg = f"Unknown preview data: {type(preview).__name__}"
            raise ValueError(msg)


def format_selection_write(
    upserted: AxiomUpsertResult | EntityUpsertResult,
    preview: SelectionPreviewData | None,
    source: WriteBlockSource,
    *,
    truncated_limit: int | None = None,
):
    """Compose the saved-line plus body for a selection-writing tool.

    Empty selection (`size == 0`): saved line + space + the variant-specific
    empty-case sentence from `_empty_message(source)`, with any trailing
    whitespace stripped (so a variant whose empty message is `""` - e.g.
    `SetExprSource` - yields just the saved line).
    Non-empty: saved line + blank line + rendered preview body, with an
    `... and N more.` footer appended (separated by a blank line) when
    `upserted.selection.size > PREVIEW_ROWS`. `preview` must be supplied
    when the selection is non-empty.
    `truncated_limit` is passed through to `format_saved_line`.
    """
    saved = format_saved_line(upserted, truncated_limit=truncated_limit)
    sel = upserted.selection

    if sel.size == 0:
        tail = _empty_message(source)
        return f"{saved} {tail}".rstrip() if tail else saved

    if preview is None:
        msg = "format_selection_write requires `preview` when the selection is non-empty"
        raise ValueError(msg)
    body = _render_preview_body(preview)

    if sel.size > PREVIEW_ROWS:
        footer = (
            f"... and {sel.size - PREVIEW_ROWS} more. Use `read_selection` with "
            f"{dquoted(sel.name)} to see all {sel.size}."
        )
        body = f"{body}\n\n{footer}"
    return f"{saved}\n\n{body}"
