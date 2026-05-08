import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from ontoloom.connection import Session
from ontoloom.errors import BadRequestError, OntoloomError
from ontoloom.hashing import HASH_DISPLAY_LEN
from ontoloom.load import load_axiom
from ontoloom.owl.axioms import Declaration
from ontoloom.owl.markers import Position
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
    SelectionItem,
    SelectionKind,
    SelectionMeta,
    SelectionPage,
    SetOp,
    ShowFilter,
)


class SelectionNotFoundError(OntoloomError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Selection {name!r} does not exist.")


class StaleSelectionError(OntoloomError):
    """Selection has changed since the caller last observed it."""

    def __init__(self, name: str, supplied_prefix: str, current_hash: str | None):
        self.name = name
        self.supplied_prefix = supplied_prefix
        self.current_hash = current_hash
        current = current_hash[:12] if current_hash else "<absent>"
        super().__init__(
            f"Selection {name!r} has changed (your prefix: {supplied_prefix!r}, "
            f"current hash: {current!r}). Re-read the selection to get the current hash."
        )


class SelectionKindError(OntoloomError):
    """Wrong selection kind for the requested operation."""

    def __init__(self, name: str, expected: SelectionKind, actual: SelectionKind, operation: str):
        self.name = name
        self.expected = expected
        self.actual = actual
        self.operation = operation
        super().__init__(
            f"'{operation}' requires an {expected} selection, "
            f"but {name!r} is an {actual} selection."
        )


@dataclass(frozen=True, slots=True)
class UpsertResult:
    selection: SelectionMeta
    previous_size: int | None


@dataclass(frozen=True, slots=True)
class DroppedSelection:
    name: str
    size: int


@dataclass(frozen=True, slots=True)
class RemoveSelectionsResult:
    dropped: tuple[DroppedSelection, ...]
    not_found: tuple[str, ...]


# A global: wrong name, should be _hash_selection. why is this applied to a list of str and not to a Selection object?
def _selection_hash(items: list[str]):
    # Use ASCII Record Separator (\x1e) -> control char that cannot appear in
    # valid IRIs/CURIEs/hashes, so two distinct item sets never collide.
    # Empty `items` always produces the same hash (SHA-256 of ""). This is
    # correct: all empty selections have identical content. To distinguish two
    # empty selections by provenance, use the name, not the hash.
    content = "\x1e".join(sorted(items))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_selection(
    s: Session, name: str
) -> SelectionMeta:  # A global: again, return type can be inferred
    """Get selection metadata. Raises SelectionNotFoundError if not found."""
    row = s.conn.execute(
        "SELECT kind, hash, size, source FROM selections WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        raise SelectionNotFoundError(name)
    return SelectionMeta(
        name=name,
        kind=SelectionKind(row[0]),
        hash=row[1],
        size=row[2],
        source=row[3],
    )


# A: function is weird, verifies stuff but returns a selection meta? this is not good
def verify_selection_hash(s: Session, name: str, hash_prefix: str) -> SelectionMeta:
    """Verify selection hasn't changed. Raises StaleSelectionError on mismatch."""
    sel = get_selection(s, name)
    if not sel.hash.startswith(hash_prefix):
        raise StaleSelectionError(name, hash_prefix, sel.hash)
    return sel


def upsert_selection(
    s: Session,
    name: str,
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
    items = list(dict.fromkeys(items))  # A global: use list(set(...)) isntead
    content_hash = _selection_hash(items)
    size = len(items)

    existing = s.conn.execute(  # A: same problem as with axioms, we may have unfortunate hash collision, so select all and if multiple error, just like with the axioms
        "SELECT size, hash FROM selections WHERE name = ?", (name,)
    ).fetchone()

    if if_hash is not None and (existing is None or not existing[1].startswith(if_hash)):
        raise StaleSelectionError(name, if_hash, existing[1] if existing else None)

    s.conn.execute("DELETE FROM selection_items WHERE selection_name = ?", (name,))
    s.conn.execute("DELETE FROM selections WHERE name = ?", (name,))
    s.conn.execute(
        "INSERT INTO selections (name, kind, hash, size, source) VALUES (?, ?, ?, ?, ?)",
        (name, kind, content_hash, size, source),
    )

    if items:
        s.conn.executemany(
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


def list_selections(s: Session) -> list[SelectionMeta]:
    return [
        SelectionMeta(
            name=r[0],
            kind=SelectionKind(r[1]),
            hash=r[2],
            size=r[3],
            source=r[4],
        )
        for r in s.conn.execute(
            "SELECT name, kind, hash, size, source FROM selections ORDER BY created_at, name"
        )
    ]


def read_selection(
    s: Session, name: str, *, limit: int = 20, offset: int = 0, show: ShowFilter = ShowFilter.ALL
) -> SelectionPage:
    # A: judgement call, is there any better way to dynamic SQL building? this is a bit meh
    if limit < 1:
        msg = f"limit must be >= 1, got {limit}."
        raise BadRequestError(msg)
    sel = get_selection(s, name)

    if sel.kind == SelectionKind.AXIOMS:
        base = (
            "FROM selection_items si "
            "LEFT JOIN axioms a ON a.hash = si.item "
            "WHERE si.selection_name = ?"
        )
        if show == ShowFilter.PRESENT:
            base += " AND a.id IS NOT NULL"
        elif show == ShowFilter.MISSING:
            base += " AND a.id IS NULL"

        total = s.conn.execute(f"SELECT COUNT(*) {base}", (name,)).fetchone()[0]
        rows = s.conn.execute(
            f"SELECT si.item, json(a.data) {base} ORDER BY si.rowid LIMIT ? OFFSET ?",
            (name, limit, offset),
        ).fetchall()

        present_count = s.conn.execute(
            "SELECT COUNT(*) FROM selection_items si "
            "JOIN axioms a ON a.hash = si.item "
            "WHERE si.selection_name = ?",
            (name,),
        ).fetchone()[0]
        missing_count = sel.size - present_count

        items = []
        # A global: important!!! do we load axioms one by one here? if yes, horrible, why not do a simple `IN` query and then append items based on if they are found or not? this does N queries for N axioms???
        for item_hash, data in rows:
            if data is None:
                items.append(SelectionItem(key=item_hash, missing=True, axiom=None))
            else:
                items.append(
                    SelectionItem(
                        key=item_hash,
                        missing=False,
                        axiom=load_axiom(
                            data, f"axiom {item_hash[:HASH_DISPLAY_LEN]} in read_selection"
                        ),
                    )
                )

    else:  # entities
        base = (
            "FROM selection_items si "
            "LEFT JOIN ("
            "  SELECT DISTINCT ae.entity_iri "
            "  FROM axiom_entities ae JOIN axioms a ON a.id = ae.axiom_id "
            f"  WHERE a.type = '{Declaration.tag()}'"
            ") decl ON decl.entity_iri = si.item "
            "WHERE si.selection_name = ?"
        )
        if show == ShowFilter.PRESENT:
            base += " AND decl.entity_iri IS NOT NULL"
        elif show == ShowFilter.MISSING:
            base += " AND decl.entity_iri IS NULL"

        total = s.conn.execute(f"SELECT COUNT(*) {base}", (name,)).fetchone()[0]
        rows = s.conn.execute(
            f"SELECT si.item, decl.entity_iri IS NOT NULL {base} ORDER BY si.rowid LIMIT ? OFFSET ?",
            (name, limit, offset),
        ).fetchall()

        present_count = s.conn.execute(
            "SELECT COUNT(DISTINCT si.item) FROM selection_items si "
            "JOIN axiom_entities ae ON ae.entity_iri = si.item "
            "JOIN axioms a ON a.id = ae.axiom_id "
            f"WHERE si.selection_name = ? AND a.type = '{Declaration.tag()}'",
            (name,),
        ).fetchone()[0]
        missing_count = sel.size - present_count

        # A: this function is unclean and complicated in general - what is all this? this is incredibly complicated and should probably be split in proper utility methods, no?

        # Batch-fetch roles and labels for present items
        present_iris = [iri for iri, is_present in rows if is_present]
        roles_map: dict[str, str] = {}
        labels_map: dict[str, str] = {}
        if present_iris:
            placeholders = ",".join("?" for _ in present_iris)
            roles_map.update(
                s.conn.execute(
                    f"SELECT DISTINCT ae.entity_iri, ae.role FROM axiom_entities ae "
                    f"JOIN axioms a ON a.id = ae.axiom_id "
                    f"WHERE a.type = '{Declaration.tag()}' AND ae.entity_iri IN ({placeholders})",
                    present_iris,
                ).fetchall()
            )
            from ontoloom.entities.store import lookup_entity_labels as _lookup_labels

            labels_map.update(
                {k: v for k, v in _lookup_labels(s, present_iris).items() if v is not None}
            )

        items = [
            SelectionItem(
                key=iri,
                missing=not is_present,
                role=roles_map.get(iri) if is_present else None,
                label=labels_map.get(iri) if is_present else None,
            )
            for iri, is_present in rows
        ]

    return SelectionPage(
        meta=sel,
        items=items,
        total_filtered=total,
        present=present_count,
        missing=missing_count,
        show=show,
    )


def remove_selections(s: Session, names: list[str]) -> RemoveSelectionsResult:
    """Best-effort remove. Duplicate names in the input are de-duplicated."""
    # A: something feels off here, not sure what it is.
    names = list(dict.fromkeys(names))
    dropped: list[DroppedSelection] = []
    not_found: list[str] = []

    for name in names:
        row = s.conn.execute("SELECT size FROM selections WHERE name = ?", (name,)).fetchone()
        if row is None:
            not_found.append(name)
        else:
            s.conn.execute("DELETE FROM selections WHERE name = ?", (name,))
            dropped.append(DroppedSelection(name=name, size=row[0]))
    return RemoveSelectionsResult(dropped=tuple(dropped), not_found=tuple(not_found))


def _glob_to_like(pattern: str):
    # A: why do we need this?????
    """Translate a glob (`*`, `?`) into a SQL LIKE pattern with `\\` escape."""
    out: list[str] = []
    for c in pattern:
        if c == "*":
            out.append("%")
        elif c == "?":
            out.append("_")
        elif c in ("%", "_", "\\"):
            out.append("\\" + c)
        else:
            out.append(c)
    return "".join(out)


def remove_selections_by_pattern(s: Session, pattern: str) -> list[DroppedSelection]:
    # A: do we even need remove_by_pattern? I guess we do, but it seems to be complciated AND we have duplicate code here with the other remove/delete stuff?
    """Remove every selection whose name matches a glob pattern.

    `pattern` uses `*` (any sequence) and `?` (one character). Returns each
    removed selection in name order.
    """
    sql_pattern = _glob_to_like(pattern)
    rows = s.conn.execute(
        "SELECT name, size FROM selections WHERE name LIKE ? ESCAPE '\\' ORDER BY name",
        (sql_pattern,),
    ).fetchall()
    dropped = [DroppedSelection(name=r[0], size=r[1]) for r in rows]
    for d in dropped:
        s.conn.execute("DELETE FROM selections WHERE name = ?", (d.name,))
    return dropped


def create_selection(s: Session, name: str, expr: SetExpr, *, source: str = "") -> UpsertResult:
    """Create a selection by evaluating a SetExpr tree."""
    items, kind = _eval_expr(s, expr)
    auto_source = source or str(expr)
    return upsert_selection(s, name, kind, items, auto_source)


def _eval_expr(s: Session, expr: SetOperand) -> tuple[list[str], SelectionKind]:
    if isinstance(expr, str):
        sel = get_selection(s, expr)
        items = [
            r[0]
            for r in s.conn.execute(
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
            raise BadRequestError(msg)
        return _axioms_for(s, items), SelectionKind.AXIOMS

    if isinstance(expr, EntitiesInExpr):
        items, kind = _eval_expr(s, expr.entities_in)
        if kind != SelectionKind.AXIOMS:
            msg = f"`entities_in` requires an axiom expression; operand is {kind}."
            raise BadRequestError(msg)
        return _entities_in(s, items, expr.field), SelectionKind.ENTITIES

    msg = f"Unknown SetExpr variant: {type(expr).__name__}"
    raise ValueError(msg)


def _eval_set_op(
    s: Session, operands: Sequence[SetOperand], op: SetOp
) -> tuple[list[str], SelectionKind]:
    if not operands:
        msg = f"'{op}' requires at least one operand."
        raise BadRequestError(msg)
    if op in (SetOp.INTERSECTION, SetOp.DIFFERENCE) and len(operands) < 2:
        msg = f"'{op}' requires at least two operands; got {len(operands)}."
        raise BadRequestError(msg)

    results = [_eval_expr(s, sub) for sub in operands]
    kinds = {kind for _, kind in results}
    if len(kinds) > 1:
        msg = f"Cannot {op}: all operands must be the same kind. Got: {sorted(kinds)}"
        raise BadRequestError(msg)
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


def _axioms_for(s: Session, entity_iris: Sequence[str]) -> list[str]:
    if not entity_iris:
        return []
    placeholders = ",".join("?" for _ in entity_iris)
    return [
        r[0]
        for r in s.conn.execute(
            f"SELECT DISTINCT a.hash FROM axioms a "
            f"JOIN axiom_entities ae ON ae.axiom_id = a.id "
            f"WHERE ae.entity_iri IN ({placeholders}) "
            f"ORDER BY a.hash",
            tuple(entity_iris),
        )
    ]


def _entities_in(s: Session, axiom_hashes: Sequence[str], field: Position | None) -> list[str]:
    if not axiom_hashes:
        return []
    placeholders = ",".join("?" for _ in axiom_hashes)
    if field is not None:
        return [
            r[0]
            for r in s.conn.execute(
                f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
                f"JOIN axioms a ON a.id = ae.axiom_id "
                f"WHERE a.hash IN ({placeholders}) AND ae.position = ? "
                f"ORDER BY ae.entity_iri",
                (*axiom_hashes, field),
            )
        ]
    return [
        r[0]
        for r in s.conn.execute(
            f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
            f"JOIN axioms a ON a.id = ae.axiom_id "
            f"WHERE a.hash IN ({placeholders}) "
            f"ORDER BY ae.entity_iri",
            tuple(axiom_hashes),
        )
    ]
