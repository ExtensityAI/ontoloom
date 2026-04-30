import hashlib

# A: this file is very long
from ontoloom.ontology.canonical import truncate_hash
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.errors import (
    BadRequestError,
    SelectionKindError,
    SelectionNotFoundError,
    StaleSelectionError,
)
from ontoloom.ontology.load import load_axiom
from ontoloom.ontology.models.axioms import Declaration
from ontoloom.ontology.models.literals import Position
from ontoloom.ontology.types import (
    ConversionOp,
    DroppedSelection,
    RemoveSelectionsResult,
    SelectionItem,
    SelectionKind,
    SelectionMeta,
    SelectionPage,
    SetOp,
    ShowFilter,
    UpsertSelectionResult,
)


# A global: wrong name, should be _hash_selection. why is this applied to a list of str and not to a Selection object?
def _selection_hash(items: list[str]):
    # Use ASCII Record Separator (\x1e) — control char that cannot appear in
    # valid IRIs/CURIEs/hashes, so two distinct item sets never collide.
    # Empty `items` always produces the same hash (SHA-256 of ""). This is
    # correct: all empty selections have identical content. To distinguish two
    # empty selections by provenance, use the name, not the hash.
    content = "\x1e".join(sorted(items))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get(ont: Ontology, name: str) -> SelectionMeta:  # A global: again, return type can be inferred
    """Get selection metadata. Raises SelectionNotFoundError if not found."""
    row = ont.conn.execute(
        "SELECT kind, hash, cardinality, source FROM selections WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        raise SelectionNotFoundError(name)
    return SelectionMeta(
        name=name,
        kind=SelectionKind(row[0]),
        hash=row[1],
        cardinality=row[2],
        source=row[3],
    )


# A: function is weird, verifies stuff but returns a selection meta? this is not good
def verify_hash(ont: Ontology, name: str, hash_prefix: str) -> SelectionMeta:
    """Verify selection hasn't changed. Raises StaleSelectionError on mismatch."""
    sel = get(ont, name)
    if not sel.hash.startswith(hash_prefix):
        raise StaleSelectionError(name, hash_prefix, sel.hash)
    return sel


def upsert(
    ont: Ontology,
    name: str,
    kind: SelectionKind,
    items: list[str],
    source: str,
    *,
    if_hash: str | None = None,
) -> UpsertSelectionResult:
    """Write a selection, overwriting if it exists.

    Items are stored in insertion order (not sorted); the hash is
    order-independent (sorted internally). Set-algebra paths (union,
    intersection, difference) pre-sort before calling upsert, so their
    insertion order is also sorted order.

    With `if_hash=None` (default), unconditional overwrite — last writer wins,
    even if another agent has written since you last read.

    With `if_hash` supplied, the existing selection's hash must start with the
    given prefix; otherwise `StaleSelectionError` is raised. Use this when the
    caller has a lock-and-update flow and wants to detect concurrent overwrites.
    """
    items = list(dict.fromkeys(items))  # A global: use list(set(...)) isntead
    content_hash = _selection_hash(items)
    cardinality = len(items)

    with ont.conn:
        existing = ont.conn.execute(  # A: same problem as with axioms, we may have unfortunate hash collision, so select all and if multiple error, just like with the axioms
            "SELECT cardinality, hash FROM selections WHERE name = ?", (name,)
        ).fetchone()

        # A global: we need proper spacing, e.g. here, we have this condition (also, stuff like this requires a comment, else hard to understand)
        if if_hash is not None and (existing is None or not existing[1].startswith(if_hash)):
            raise StaleSelectionError(name, if_hash, existing[1] if existing else None)
        # A global: I feel like these should be utility methods or sth? not sure, if only used here fine, but I feel like the delete op on the db could be moved out if used in multiple locations. in this way, do a pass for SQL that is used in multiple places, good candidates! also for code simplicity!
        ont.conn.execute("DELETE FROM selection_items WHERE selection_name = ?", (name,))
        ont.conn.execute("DELETE FROM selections WHERE name = ?", (name,))
        ont.conn.execute(
            "INSERT INTO selections (name, kind, hash, cardinality, source) VALUES (?, ?, ?, ?, ?)",
            (name, kind, content_hash, cardinality, source),
        )
        if items:
            ont.conn.executemany(
                "INSERT INTO selection_items (selection_name, item) VALUES (?, ?)",
                [(name, item) for item in items],
            )

    return UpsertSelectionResult(
        content_hash=content_hash,
        cardinality=cardinality,
        old_cardinality=existing[0] if existing else None,
    )


def list_all(ont: Ontology) -> list[SelectionMeta]:
    return [
        SelectionMeta(
            name=r[0],
            kind=SelectionKind(r[1]),
            hash=r[2],
            cardinality=r[3],
            source=r[4],
        )
        for r in ont.conn.execute(
            "SELECT name, kind, hash, cardinality, source FROM selections ORDER BY created_at, name"
        )
    ]


def read(
    ont: Ontology, name: str, *, limit: int = 20, offset: int = 0, show: ShowFilter = ShowFilter.ALL
) -> SelectionPage:
    # A: judgement call, is there any better way to dynamic SQL building? this is a bit meh
    if limit < 1:
        msg = f"limit must be >= 1, got {limit}."
        raise BadRequestError(msg)
    sel = get(ont, name)

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

        total = ont.conn.execute(f"SELECT COUNT(*) {base}", (name,)).fetchone()[0]
        rows = ont.conn.execute(
            f"SELECT si.item, json(a.data) {base} ORDER BY si.rowid LIMIT ? OFFSET ?",
            (name, limit, offset),
        ).fetchall()

        present_count = ont.conn.execute(
            "SELECT COUNT(*) FROM selection_items si "
            "JOIN axioms a ON a.hash = si.item "
            "WHERE si.selection_name = ?",
            (name,),
        ).fetchone()[0]
        missing_count = sel.cardinality - present_count

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
                            data, f"axiom {truncate_hash(item_hash)} in read_selection"
                        ),
                    )
                )

    else:  # entities
        base = (
            "FROM selection_items si "
            "LEFT JOIN ("
            "  SELECT DISTINCT ae.entity_iri "
            "  FROM axiom_entities ae JOIN axioms a ON a.id = ae.axiom_id "
            f"  WHERE a.type = '{Declaration.type_}'"
            ") decl ON decl.entity_iri = si.item "
            "WHERE si.selection_name = ?"
        )
        if show == ShowFilter.PRESENT:
            base += " AND decl.entity_iri IS NOT NULL"
        elif show == ShowFilter.MISSING:
            base += " AND decl.entity_iri IS NULL"

        total = ont.conn.execute(f"SELECT COUNT(*) {base}", (name,)).fetchone()[0]
        rows = ont.conn.execute(
            f"SELECT si.item, decl.entity_iri IS NOT NULL {base} ORDER BY si.rowid LIMIT ? OFFSET ?",
            (name, limit, offset),
        ).fetchall()

        present_count = ont.conn.execute(
            "SELECT COUNT(DISTINCT si.item) FROM selection_items si "
            "JOIN axiom_entities ae ON ae.entity_iri = si.item "
            "JOIN axioms a ON a.id = ae.axiom_id "
            f"WHERE si.selection_name = ? AND a.type = '{Declaration.type_}'",
            (name,),
        ).fetchone()[0]
        missing_count = sel.cardinality - present_count

        # A: this function is unclean and complicated in general - what is all this? this is incredibly complicated and should probably be split in proper utility methods, no?

        # Batch-fetch roles and labels for present items
        present_iris = [iri for iri, is_present in rows if is_present]
        roles_map: dict[str, str] = {}
        labels_map: dict[str, str] = {}
        if present_iris:
            placeholders = ",".join("?" for _ in present_iris)
            roles_map.update(
                ont.conn.execute(
                    f"SELECT DISTINCT ae.entity_iri, ae.role FROM axiom_entities ae "
                    f"JOIN axioms a ON a.id = ae.axiom_id "
                    f"WHERE a.type = '{Declaration.type_}' AND ae.entity_iri IN ({placeholders})",
                    present_iris,
                ).fetchall()
            )
            from ontoloom.ontology.entities import lookup_labels as _lookup_labels

            labels_map.update(
                {k: v for k, v in _lookup_labels(ont, present_iris).items() if v is not None}
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


def remove(ont: Ontology, names: list[str]) -> RemoveSelectionsResult:
    """Best-effort remove. Duplicate names in the input are de-duplicated."""
    # A: something feels off here, not sure what it is.
    names = list(dict.fromkeys(names))
    dropped: list[DroppedSelection] = []
    not_found: list[str] = []
    with ont.conn:
        for name in names:
            row = ont.conn.execute(
                "SELECT cardinality FROM selections WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                not_found.append(name)
            else:
                ont.conn.execute("DELETE FROM selections WHERE name = ?", (name,))
                dropped.append(DroppedSelection(name=name, cardinality=row[0]))
    return RemoveSelectionsResult(dropped=dropped, not_found=not_found)


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


def remove_by_pattern(ont: Ontology, pattern: str) -> list[DroppedSelection]:
    # A: do we even need remove_by_pattern? I guess we do, but it seems to be complciated AND we have duplicate code here with the other remove/delete stuff?
    """Remove every selection whose name matches a glob pattern.

    `pattern` uses `*` (any sequence) and `?` (one character). Returns each
    removed selection in name order.
    """
    sql_pattern = _glob_to_like(pattern)
    with ont.conn:
        rows = ont.conn.execute(
            "SELECT name, cardinality FROM selections WHERE name LIKE ? ESCAPE '\\' ORDER BY name",
            (sql_pattern,),
        ).fetchall()
        dropped = [DroppedSelection(name=r[0], cardinality=r[1]) for r in rows]
        for d in dropped:
            ont.conn.execute("DELETE FROM selections WHERE name = ?", (d.name,))
    return dropped


def create(
    ont: Ontology,
    name: str,
    *,
    # Flat kwargs rather than a discriminated op type for MCP JSON-schema compatibility.
    union: list[str] | None = None,
    intersection: list[str] | None = None,
    difference: list[str] | None = None,
    axioms_for: str | None = None,
    entities_in: str | None = None,
    field: Position | None = None,
    source: str = "",
) -> UpsertSelectionResult:
    # A: args are very unclear - is this a bit of a god function? why can we not do a discriminated op type for MCP JSON schema compatibility? seems complex and useless?
    """Create a selection from set algebra or type conversion."""
    ops = [
        x for x in [union, intersection, difference, axioms_for, entities_in] if x is not None
    ]  # A: what is this? this is horrible???
    if len(ops) != 1:
        msg = "Exactly one operation must be provided (union, intersection, difference, axioms_for, or entities_in)."
        raise BadRequestError(msg)

    if field is not None and entities_in is None:
        msg = "The 'field' parameter is only valid with 'entities_in'."  # A: does not provide any info on why or what etc
        raise BadRequestError(msg)

    if union is not None:
        return _create_from_set_op(ont, SetOp.UNION, name, union, source)
    if intersection is not None:
        return _create_from_set_op(ont, SetOp.INTERSECTION, name, intersection, source)
    if difference is not None:
        return _create_from_set_op(ont, SetOp.DIFFERENCE, name, difference, source)
    if axioms_for is not None:
        return _create_from_conversion(ont, name, axioms_for, ConversionOp.AXIOMS_FOR, source)
    assert entities_in is not None
    return _create_from_conversion(
        ont, name, entities_in, ConversionOp.ENTITIES_IN, source, field=field
    )


def _create_from_set_op(
    ont: Ontology, op: SetOp, name: str, inputs: list[str], source: str
) -> UpsertSelectionResult:
    if not inputs:
        msg = f"'{op}' requires at least one selection name."
        raise BadRequestError(msg)
    if op in (SetOp.INTERSECTION, SetOp.DIFFERENCE) and len(inputs) < 2:
        msg = f"'{op}' requires at least two selection names; got 1."
        raise BadRequestError(msg)

    # A: we need to look at this function. for this, talk to me, we will think through how this could be improved. this is horrible rn.

    kind_map = {n: get(ont, n).kind for n in inputs}
    kinds = set(kind_map.values())
    if len(kinds) > 1:
        details = ", ".join(f"{n!r} ({kind_map[n]})" for n in inputs)
        msg = f"Cannot {op}: all inputs must be the same kind. Got: {details}"
        raise BadRequestError(msg)
    kind = kinds.pop()

    match op:
        case SetOp.UNION:
            placeholders = ",".join("?" for _ in inputs)
            # ORDER BY item: insertion order into selection_items.rowid is the
            # pagination key for read_selection (see P-09-1).
            items = [
                r[0]
                for r in ont.conn.execute(
                    f"SELECT DISTINCT item FROM selection_items "
                    f"WHERE selection_name IN ({placeholders}) ORDER BY item",
                    inputs,
                )
            ]
        case SetOp.INTERSECTION:
            first, *rest = inputs
            items_set = {
                r[0]
                for r in ont.conn.execute(
                    "SELECT item FROM selection_items WHERE selection_name = ?", (first,)
                )
            }
            for other in rest:
                other_items = {
                    r[0]
                    for r in ont.conn.execute(
                        "SELECT item FROM selection_items WHERE selection_name = ?", (other,)
                    )
                }
                items_set &= other_items
            items = sorted(items_set)
        case SetOp.DIFFERENCE:
            first, *rest = inputs
            items_set = {
                r[0]
                for r in ont.conn.execute(
                    "SELECT item FROM selection_items WHERE selection_name = ?", (first,)
                )
            }
            for other in rest:
                other_items = {
                    r[0]
                    for r in ont.conn.execute(
                        "SELECT item FROM selection_items WHERE selection_name = ?", (other,)
                    )
                }
                items_set -= other_items
            items = sorted(items_set)
        case _:
            msg = f"Unknown set operation: {op}"
            raise ValueError(msg)

    auto_source = source or f"{op.value}({', '.join(repr(n) for n in inputs)})"
    return upsert(ont, name, kind, items, auto_source)


def _create_from_conversion(
    ont: Ontology,
    name: str,
    input_name: str,
    op: ConversionOp,
    source: str,
    *,
    field: Position | None = None,
) -> UpsertSelectionResult:
    sel = get(ont, input_name)
    # A: we also need to look at this function together, is also horrible.
    # A global: is get(...) a good name? if we always import selections then yes, because of selections.get, but I feel like get_selection is still superior, as it is more clear. same for other funcs like that!

    if op == ConversionOp.AXIOMS_FOR:
        if sel.kind != SelectionKind.ENTITIES:
            raise SelectionKindError(
                name=input_name,
                expected=SelectionKind.ENTITIES,
                actual=sel.kind,
                operation="create_selection",
            )
        items = [
            r[0]
            for r in ont.conn.execute(
                "SELECT DISTINCT a.hash FROM axioms a "
                "JOIN axiom_entities ae ON ae.axiom_id = a.id "
                "WHERE ae.entity_iri IN (SELECT item FROM selection_items WHERE selection_name = ?) "
                "ORDER BY a.hash",
                (input_name,),
            )
        ]
        kind = SelectionKind.AXIOMS
    else:  # entities_in
        if sel.kind != SelectionKind.AXIOMS:
            raise SelectionKindError(
                name=input_name,
                expected=SelectionKind.AXIOMS,
                actual=sel.kind,
                operation="create_selection",
            )
        if field is not None and field != Position.ANY:
            items = [
                r[0]
                for r in ont.conn.execute(
                    "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
                    "JOIN axioms a ON a.id = ae.axiom_id "
                    "WHERE a.hash IN (SELECT item FROM selection_items WHERE selection_name = ?) "
                    "AND ae.position = ? ORDER BY ae.entity_iri",
                    (input_name, field),
                )
            ]
        else:
            items = [
                r[0]
                for r in ont.conn.execute(
                    "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
                    "JOIN axioms a ON a.id = ae.axiom_id "
                    "WHERE a.hash IN (SELECT item FROM selection_items WHERE selection_name = ?) "
                    "ORDER BY ae.entity_iri",
                    (input_name,),
                )
            ]
        kind = SelectionKind.ENTITIES

    auto_source = source or f"{op}({input_name!r})"
    return upsert(ont, name, kind, items, auto_source)
