import hashlib
from enum import StrEnum

from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.errors import (
    SelectionKindError,
    SelectionNotFoundError,
    StaleSelectionError,
)
from ontoloom.ontology.load import load_axiom
from ontoloom.ontology.types import (
    Position,
    SelectionItem,
    SelectionKind,
    SelectionMeta,
    SelectionPage,
    ShowFilter,
)


class SetOp(StrEnum):
    UNION = "union"
    INTERSECTION = "intersection"
    DIFFERENCE = "difference"


class ConversionOp(StrEnum):
    AXIOMS_FOR = "axioms_for"
    ENTITIES_IN = "entities_in"


def _selection_hash(items: list[str]) -> str:
    content = "\n".join(sorted(items))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_info(ont: Ontology, name: str) -> SelectionMeta:
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


def verify_hash(ont: Ontology, name: str, hash_prefix: str) -> SelectionMeta:
    """Verify selection hasn't changed. Raises StaleSelectionError on mismatch."""
    sel = get_info(ont, name)
    if not sel.hash.startswith(hash_prefix):
        raise StaleSelectionError(name)
    return sel


def write(
    ont: Ontology, name: str, kind: SelectionKind, items: list[str], source: str
) -> tuple[str, int, int | None]:
    """Write a selection, overwriting if it exists. Returns (hash, cardinality, old_cardinality)."""
    items = list(dict.fromkeys(items))
    content_hash = _selection_hash(items)
    cardinality = len(items)

    overwrote = ont.conn.execute(
        "SELECT cardinality FROM selections WHERE name = ?", (name,)
    ).fetchone()

    with ont.conn:
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

    old_cardinality = overwrote[0] if overwrote else None
    return content_hash, cardinality, old_cardinality


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
            "SELECT name, kind, hash, cardinality, source FROM selections ORDER BY created_at"
        )
    ]


def read(
    ont: Ontology, name: str, *, limit: int = 20, offset: int = 0, show: ShowFilter = ShowFilter.ALL
) -> SelectionPage:
    if limit < 1:
        msg = f"limit must be >= 1, got {limit}."
        raise ValueError(msg)
    sel = get_info(ont, name)

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
        for item_hash, data in rows:
            if data is None:
                items.append(SelectionItem(key=item_hash, missing=True, axiom=None))
            else:
                items.append(
                    SelectionItem(
                        key=item_hash,
                        missing=False,
                        axiom=load_axiom(data, f"axiom {item_hash[:8]} in read_selection"),
                    )
                )

    else:  # entities
        base = (
            "FROM selection_items si "
            "LEFT JOIN ("
            "  SELECT DISTINCT ae.entity_iri "
            "  FROM axiom_entities ae JOIN axioms a ON a.id = ae.axiom_id "
            "  WHERE a.type = 'Declaration'"
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
            "SELECT COUNT(*) FROM selection_items si "
            "JOIN axiom_entities ae ON ae.entity_iri = si.item "
            "JOIN axioms a ON a.id = ae.axiom_id "
            "WHERE si.selection_name = ? AND a.type = 'Declaration'",
            (name,),
        ).fetchone()[0]
        missing_count = sel.cardinality - present_count

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
                    f"WHERE a.type = 'Declaration' AND ae.entity_iri IN ({placeholders})",
                    present_iris,
                ).fetchall()
            )
            labels_map.update(
                ont.conn.execute(
                    f"SELECT entity_iri, text FROM entity_text "
                    f"WHERE property = 'rdfs:label' AND entity_iri IN ({placeholders})",
                    present_iris,
                ).fetchall()
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


def remove(ont: Ontology, names: list[str]) -> tuple[list[tuple[str, int]], list[str]]:
    """Best-effort remove. Returns (dropped, not_found)."""
    dropped = []
    not_found = []
    with ont.conn:
        for name in names:
            row = ont.conn.execute(
                "SELECT cardinality FROM selections WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                not_found.append(name)
            else:
                ont.conn.execute("DELETE FROM selections WHERE name = ?", (name,))
                dropped.append((name, row[0]))
    return dropped, not_found


def create(
    ont: Ontology,
    name: str,
    *,
    union: list[str] | None = None,
    intersection: list[str] | None = None,
    difference: list[str] | None = None,
    axioms_for: str | None = None,
    entities_in: str | None = None,
    field: Position | None = None,
    source: str = "",
) -> tuple[str, int, int | None]:
    """Create a selection from set algebra or type conversion."""
    ops = [x for x in [union, intersection, difference, axioms_for, entities_in] if x is not None]
    if len(ops) != 1:
        msg = "Exactly one operation must be provided (union, intersection, difference, axioms_for, or entities_in)."
        raise ValueError(msg)

    if field is not None and entities_in is None:
        msg = "The 'field' parameter is only valid with 'entities_in'."
        raise ValueError(msg)

    if union is not None:
        return _create_from_set_op(ont, SetOp.UNION, name, union, source)
    if intersection is not None:
        return _create_from_set_op(ont, SetOp.INTERSECTION, name, intersection, source)
    if difference is not None:
        return _create_from_set_op(ont, SetOp.DIFFERENCE, name, difference, source)
    if axioms_for is not None:
        return _create_from_conversion(ont, name, axioms_for, ConversionOp.AXIOMS_FOR, source)
    return _create_from_conversion(
        ont, name, entities_in, ConversionOp.ENTITIES_IN, source, field=field
    )  # pyright: ignore[reportArgumentType]


def _create_from_set_op(
    ont: Ontology, op: SetOp, name: str, inputs: list[str], source: str
) -> tuple[str, int, int | None]:
    if not inputs:
        msg = f"'{op}' requires at least one selection name."
        raise ValueError(msg)

    kinds: set[SelectionKind] = set()
    for input_name in inputs:
        sel = get_info(ont, input_name)
        kinds.add(sel.kind)
    if len(kinds) > 1:
        details = ", ".join(f"{n!r} ({get_info(ont, n).kind})" for n in inputs)
        msg = f"Cannot {op}: all inputs must be the same kind. Got: {details}"
        raise ValueError(msg)
    kind = kinds.pop()

    match op:
        case SetOp.UNION:
            placeholders = ",".join("?" for _ in inputs)
            items = [
                r[0]
                for r in ont.conn.execute(
                    f"SELECT DISTINCT item FROM selection_items WHERE selection_name IN ({placeholders})",
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
            items = list(items_set)
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
            items = list(items_set)
        case _:
            msg = f"Unknown set operation: {op}"
            raise ValueError(msg)

    auto_source = source or f"{op.value}({', '.join(repr(n) for n in inputs)})"
    return write(ont, name, kind, items, auto_source)


def _create_from_conversion(
    ont: Ontology,
    name: str,
    input_name: str,
    op: ConversionOp,
    source: str,
    *,
    field: Position | None = None,
) -> tuple[str, int, int | None]:
    sel = get_info(ont, input_name)

    if op == ConversionOp.AXIOMS_FOR:
        if sel.kind != SelectionKind.ENTITIES:
            raise SelectionKindError(
                name=input_name, expected="entities", actual=sel.kind, operation="axioms_for"
            )
        items = [
            r[0]
            for r in ont.conn.execute(
                "SELECT DISTINCT a.hash FROM axioms a "
                "JOIN axiom_entities ae ON ae.axiom_id = a.id "
                "WHERE ae.entity_iri IN (SELECT item FROM selection_items WHERE selection_name = ?)",
                (input_name,),
            )
        ]
        kind = SelectionKind.AXIOMS
    else:  # entities_in
        if sel.kind != SelectionKind.AXIOMS:
            raise SelectionKindError(
                name=input_name, expected="axioms", actual=sel.kind, operation="entities_in"
            )
        if field is not None and field != Position.ANY:
            items = [
                r[0]
                for r in ont.conn.execute(
                    "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
                    "JOIN axioms a ON a.id = ae.axiom_id "
                    "WHERE a.hash IN (SELECT item FROM selection_items WHERE selection_name = ?) "
                    "AND ae.position = ?",
                    (input_name, field),
                )
            ]
        else:
            items = [
                r[0]
                for r in ont.conn.execute(
                    "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
                    "JOIN axioms a ON a.id = ae.axiom_id "
                    "WHERE a.hash IN (SELECT item FROM selection_items WHERE selection_name = ?)",
                    (input_name,),
                )
            ]
        kind = SelectionKind.ENTITIES

    auto_source = source or f"{op}({input_name!r})"
    return write(ont, name, kind, items, auto_source)
