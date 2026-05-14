import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated

from pydantic import Field

from ontoloom.connection import Session
from ontoloom.hashing import AxiomHash
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import Position
from ontoloom.query._constraints import (
    EntityConstraint,
    InPositions,
    MentionedInAxioms,
    MentionsAny,
)
from ontoloom.query._dispatch import run
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.query.list_axiom_hashes import ListAxiomHashes
from ontoloom.query.list_entities import ListEntities
from ontoloom.query.read_axiom_selection import ReadAxiomSelection
from ontoloom.query.read_entity_selection import ReadEntitySelection
from ontoloom.selections.expr import (
    AxiomsForExpr,
    DiffExpr,
    EntitiesInExpr,
    IntersectExpr,
    SetExpr,
    SetOperand,
    UnionExpr,
)
from ontoloom.selections.types import (
    AxiomSelectionPage,
    EntitySelectionPage,
    LockedSelection,
    SelectionContentHash,
    SelectionExprError,
    SelectionKind,
    SelectionKindError,
    SelectionListing,
    SelectionMeta,
    SelectionName,
    SelectionNotFoundError,
    SetOp,
    ShowFilter,
    StaleSelectionError,
)
from ontoloom.utils import dedupe, dquoted


@dataclass(frozen=True, slots=True)
class UpsertResult:
    selection: SelectionMeta
    previous_size: int | None


@dataclass(frozen=True, slots=True)
class DroppedSelection:
    name: SelectionName
    size: int


@dataclass(frozen=True, slots=True)
class RemoveSelectionsResult:
    dropped: tuple[DroppedSelection, ...]
    not_found: tuple[SelectionName, ...]


def _hash_selection_items(items: list[str]) -> SelectionContentHash:
    # Use ASCII Record Separator (\x1e) -> control char that cannot appear in
    # valid IRIs/CURIEs/hashes, so two distinct item sets never collide.
    # Empty `items` always produces the same hash (SHA-256 of ""). This is
    # correct: all empty selections have identical content. To distinguish two
    # empty selections by provenance, use the name, not the hash.
    content = "\x1e".join(sorted(items))
    return SelectionContentHash(hashlib.sha256(content.encode()).hexdigest()[:16])


def get_selection(s: Session, name: SelectionName):
    """Get selection metadata. Raises SelectionNotFoundError if not found."""
    row = s._conn.execute(
        "SELECT kind, hash, size, source FROM selections WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        raise SelectionNotFoundError(name)
    return SelectionMeta(
        name=name,
        kind=SelectionKind(row[0]),
        hash=SelectionContentHash(row[1]),
        size=row[2],
        source=row[3],
    )


def get_locked_selection(s: Session, locked: LockedSelection):
    """Fetch a selection by name, requiring its current hash to match `locked.hash_prefix`.

    Raises StaleSelectionError if the lock doesn't match.
    """
    sel = get_selection(s, locked.name)

    if not sel.hash.startswith(locked.hash_prefix):
        raise StaleSelectionError(locked.name, locked.hash_prefix, sel.hash, sel.size)

    return sel


def require_locked_selection(
    s: Session,
    within: LockedSelection,
    expected_kind: SelectionKind,
    operation: str,
) -> SelectionMeta:
    """Lock-check `within` and require its kind matches.

    Raises:
        StaleSelectionError: if `within.hash_prefix` no longer matches.
        SelectionKindError: if the selection exists but is the wrong kind.
    """
    sel = get_locked_selection(s, within)

    if sel.kind != expected_kind:
        raise SelectionKindError(
            name=within.name,
            expected=expected_kind,
            actual=sel.kind,
            operation=operation,
        )
    return sel


def upsert_selection(
    s: Session,
    name: SelectionName,
    kind: SelectionKind,
    items: Sequence[str],
    source: str,
    *,
    if_hash: str | None = None,
) -> UpsertResult:
    """Write a selection, overwriting if it exists.

    Items are stored in insertion order (not sorted); the hash is
    order-independent (sorted internally). Set-algebra paths (union,
    intersection, difference) pre-sort before calling upsert, so their
    insertion order is also sorted order.

    With `if_hash=None` (default), unconditional overwrite -> last writer wins,
    even if another agent has written since you last read.

    With `if_hash` supplied, the existing selection's hash must start with the
    given prefix; otherwise `StaleSelectionError` is raised. Use this when the
    caller has a lock-and-update flow and wants to detect concurrent overwrites.
    """
    items = dedupe(items)
    content_hash = _hash_selection_items(items)
    size = len(items)

    existing = s._conn.execute(
        "SELECT size, hash FROM selections WHERE name = ?", (name,)
    ).fetchone()

    if if_hash is not None and (existing is None or not existing[1].startswith(if_hash)):
        raise StaleSelectionError(
            name,
            if_hash,
            existing[1] if existing else None,
            existing[0] if existing else None,
        )

    s._conn.execute("DELETE FROM selection_items WHERE selection_name = ?", (name,))
    s._conn.execute("DELETE FROM selections WHERE name = ?", (name,))
    s._conn.execute(
        "INSERT INTO selections (name, kind, hash, size, source) VALUES (?, ?, ?, ?, ?)",
        (name, kind, content_hash, size, source),
    )

    if items:
        s._conn.executemany(
            "INSERT INTO selection_items (selection_name, item) VALUES (?, ?)",
            [(name, item) for item in items],
        )

    return UpsertResult(
        selection=SelectionMeta(
            name=name,
            kind=kind,
            hash=content_hash,
            size=size,
            source=source,
        ),
        previous_size=existing[0] if existing else None,
    )


def list_selections(s: Session) -> list[SelectionListing]:
    """Return all selections paired with their current present-item count.

    Drift detection: `missing_count = meta.size - present_count`. Item is
    "present" iff it still resolves — for axiom selections, the hash exists in
    `axioms`; for entity selections, the IRI is referenced by any axiom
    (declared or not).
    """
    metas = [
        SelectionMeta(
            name=SelectionName(r[0]),
            kind=SelectionKind(r[1]),
            hash=r[2],
            size=r[3],
            source=r[4],
        )
        for r in s._conn.execute(
            "SELECT name, kind, hash, size, source FROM selections ORDER BY created_at, name"
        )
    ]

    if not metas:
        return []

    # Batched present-count queries — one per kind. Selections with zero items
    # produce count=0 via the LEFT JOIN's NULL row.
    axiom_present: dict[str, int] = dict(
        s._conn.execute(
            "SELECT s.name, COUNT(a.hash) "
            "FROM selections s "
            "LEFT JOIN selection_items si ON si.selection_name = s.name "
            "LEFT JOIN axioms a ON a.hash = si.item "
            "WHERE s.kind = ? "
            "GROUP BY s.name",
            (SelectionKind.AXIOMS.value,),
        )
    )
    entity_present: dict[str, int] = dict(
        s._conn.execute(
            "SELECT s.name, COUNT(DISTINCT CASE WHEN ae.entity_iri IS NOT NULL THEN si.item END) "
            "FROM selections s "
            "LEFT JOIN selection_items si ON si.selection_name = s.name "
            "LEFT JOIN axiom_entities ae ON ae.entity_iri = si.item "
            "WHERE s.kind = ? "
            "GROUP BY s.name",
            (SelectionKind.ENTITIES.value,),
        )
    )

    return [
        SelectionListing(
            meta=meta,
            present_count=(
                axiom_present.get(meta.name, 0)
                if meta.kind == SelectionKind.AXIOMS
                else entity_present.get(meta.name, 0)
            ),
        )
        for meta in metas
    ]


def read_selection(
    s: Session,
    name: SelectionName,
    *,
    limit: Annotated[int, Field(ge=1)] = 20,
    offset: int = 0,
    show: ShowFilter = ShowFilter.ALL,
) -> AxiomSelectionPage | EntitySelectionPage:
    sel = get_selection(s, name)
    ref = ResolvedSelection(kind=sel.kind, bare_name=str(name))

    if sel.kind == SelectionKind.AXIOMS:
        return run(s, ReadAxiomSelection(selection=ref, limit=limit, offset=offset, show=show))
    return run(s, ReadEntitySelection(selection=ref, limit=limit, offset=offset, show=show))


def _remove_by_names(s: Session, names: Sequence[SelectionName]) -> list[DroppedSelection]:
    """Delete the named selections in one batch; return what was actually dropped."""
    if not names:
        return []
    placeholders = ",".join("?" for _ in names)
    dropped = [
        DroppedSelection(name=SelectionName(r[0]), size=r[1])
        for r in s._conn.execute(
            f"SELECT name, size FROM selections WHERE name IN ({placeholders}) ORDER BY name",
            tuple(names),
        )
    ]
    if dropped:
        s._conn.execute(
            f"DELETE FROM selections WHERE name IN ({placeholders})",
            tuple(names),
        )
    return dropped


def remove_selections(s: Session, names: list[SelectionName]) -> RemoveSelectionsResult:
    """Best-effort remove. Duplicate names in the input are de-duplicated."""
    deduped = dedupe(names)
    dropped = _remove_by_names(s, deduped)
    found = {d.name for d in dropped}
    not_found = tuple(n for n in deduped if n not in found)
    return RemoveSelectionsResult(dropped=tuple(dropped), not_found=not_found)


def create_selection(
    s: Session, name: SelectionName, expr: SetExpr, *, source: str = ""
) -> UpsertResult:
    """Create a selection by evaluating a SetExpr tree."""
    items, kind = _eval_expr(s, expr)
    auto_source = source or str(expr)
    return upsert_selection(s, name, kind, items, auto_source)


def _eval_expr(s: Session, expr: SetOperand) -> tuple[Sequence[str], SelectionKind]:
    if isinstance(expr, str):
        sel = get_selection(s, SelectionName(expr))
        items = [
            r[0]
            for r in s._conn.execute(
                "SELECT item FROM selection_items WHERE selection_name = ? ORDER BY rowid",
                (expr,),
            )
        ]
        return items, sel.kind

    if isinstance(expr, UnionExpr):
        return _eval_set_op(s, expr.union, SetOp.UNION)
    if isinstance(expr, IntersectExpr):
        return _eval_set_op(s, expr.intersect, SetOp.INTERSECTION)
    if isinstance(expr, DiffExpr):
        return _eval_set_op(s, expr.diff, SetOp.DIFFERENCE)

    if isinstance(expr, AxiomsForExpr):
        items, kind = _eval_expr(s, expr.axioms_for)
        if kind != SelectionKind.ENTITIES:
            msg = f"`axioms_for` requires an entity expression; operand is {kind}."
            raise SelectionExprError(msg)
        return _axioms_for(s, items), SelectionKind.AXIOMS

    if isinstance(expr, EntitiesInExpr):
        items, kind = _eval_expr(s, expr.entities_in)
        if kind != SelectionKind.AXIOMS:
            msg = f"`entities_in` requires an axiom expression; operand is {kind}."
            raise SelectionExprError(msg)
        return _entities_in(s, items, expr.field), SelectionKind.ENTITIES

    msg = f"Unknown SetExpr variant: {type(expr).__name__}"
    raise ValueError(msg)


def _eval_set_op(
    s: Session, operands: Sequence[SetOperand], op: SetOp
) -> tuple[Sequence[str], SelectionKind]:
    if not operands:
        msg = f"{dquoted(op)} requires at least one operand."
        raise SelectionExprError(msg)
    if op in (SetOp.INTERSECTION, SetOp.DIFFERENCE) and len(operands) < 2:
        msg = f"{dquoted(op)} requires at least two operands; got {len(operands)}."
        raise SelectionExprError(msg)

    results = [_eval_expr(s, sub) for sub in operands]
    kinds = {kind for _, kind in results}
    if len(kinds) > 1:
        msg = f"Cannot {op}: all operands must be the same kind. Got: {sorted(kinds)}"
        raise SelectionExprError(msg)
    kind = kinds.pop()

    match op:
        case SetOp.UNION:
            items_set: set[str] = set()
            for op_items, _ in results:
                items_set |= set(op_items)
        case SetOp.INTERSECTION:
            items_set = set(results[0][0])
            for op_items, _ in results[1:]:
                items_set &= set(op_items)
        case SetOp.DIFFERENCE:
            items_set = set(results[0][0])
            for op_items, _ in results[1:]:
                items_set -= set(op_items)
        case _:
            msg = f"Unknown set operation: {op}"
            raise ValueError(msg)

    return sorted(items_set), kind


def _axioms_for(s: Session, entity_iris: Sequence[str]) -> list[AxiomHash]:
    if not entity_iris:
        return []
    return run(
        s,
        ListAxiomHashes(
            constraints=(MentionsAny(iris=tuple(IRI(i) for i in entity_iris)),),
        ),
    )


def _entities_in(s: Session, axiom_hashes: Sequence[str], field: Position | None) -> list[IRI]:
    if not axiom_hashes:
        return []
    constraints: list[EntityConstraint] = [
        MentionedInAxioms(hashes=tuple(AxiomHash(h) for h in axiom_hashes))
    ]
    if field is not None:
        constraints.append(InPositions(positions=(field,)))
    return run(s, ListEntities(constraints=tuple(constraints)))
