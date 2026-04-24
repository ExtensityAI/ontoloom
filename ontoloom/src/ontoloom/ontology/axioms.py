import re
from collections import Counter

from ontoloom.ontology import selections
from ontoloom.ontology.canonical import axiom_hash
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.errors import (
    AmbiguousHashError,
    AxiomNotFoundError,
    InvalidHashError,
    SelectionKindError,
)
from ontoloom.ontology.indexes import _extract_annotation_value, populate
from ontoloom.ontology.load import load_axiom
from ontoloom.ontology.models.axioms import Axiom
from ontoloom.ontology.models.literals import IRI, Annotation
from ontoloom.ontology.types import AddResult, HashedAxiom, RemoveResult, SearchPage, SelectionKind

_HEX_RE = re.compile(r"^[0-9a-f]+$")


def _log_event(ont: Ontology, op: str, axiom_hash: str, axiom_json: str | None = None):
    if axiom_json is not None:
        ont.conn.execute(
            "INSERT INTO events (session_id, op, axiom_hash, axiom_json) VALUES (?, ?, ?, jsonb(?))",
            (ont.session_id, op, axiom_hash, axiom_json),
        )
    else:
        ont.conn.execute(
            "INSERT INTO events (session_id, op, axiom_hash) VALUES (?, ?, ?)",
            (ont.session_id, op, axiom_hash),
        )


def add(ont: Ontology, axioms: list[Axiom]) -> AddResult:
    added: list[HashedAxiom] = []
    skipped: list[HashedAxiom] = []

    with ont.conn:
        for axiom in axioms:
            h = axiom_hash(axiom)
            json_data = axiom.model_dump_json()
            cursor = ont.conn.execute(
                "INSERT OR IGNORE INTO axioms (hash, type, data) VALUES (?, ?, jsonb(?))",
                (h, axiom.type, json_data),
            )
            ha = HashedAxiom(axiom=axiom, hash=h)

            if cursor.rowcount == 0:
                skipped.append(ha)
                continue

            added.append(ha)
            axiom_id = cursor.lastrowid
            if axiom_id is None:
                msg = "INSERT succeeded but lastrowid is None"
                raise RuntimeError(msg)
            _log_event(ont, "add", h, json_data)
            populate(ont, axiom, axiom_id)

    return AddResult(added=added, skipped=skipped)


def remove_by_hash(ont: Ontology, hash_prefixes: list[str]) -> RemoveResult:
    for prefix in hash_prefixes:
        if not _HEX_RE.match(prefix):
            raise InvalidHashError(prefix)

    with ont.conn:
        to_remove: list[HashedAxiom] = []
        for prefix in hash_prefixes:
            rows = ont.conn.execute(
                "SELECT hash, json(data) FROM axioms WHERE hash LIKE ? || '%'",
                (prefix,),
            ).fetchall()

            if not rows:
                raise AxiomNotFoundError(prefix)
            if len(rows) > 1:
                samples = [r[0][:8] for r in rows]
                raise AmbiguousHashError(prefix, len(rows), samples)

            full_hash, json_data = rows[0]
            axiom = load_axiom(json_data, f"axiom {full_hash[:8]} in remove_by_hash")
            to_remove.append(HashedAxiom(axiom=axiom, hash=full_hash))

        for ha in to_remove:
            _log_event(ont, "del", ha.hash)
            ont.conn.execute("DELETE FROM axioms WHERE hash = ?", (ha.hash,))

    return RemoveResult(removed=to_remove)


def remove_by_selection(
    ont: Ontology, name: str, hash_prefix: str
) -> tuple[list[HashedAxiom], int]:
    """Remove axioms referenced by an axiom selection. Best-effort: skips missing."""
    sel = selections.verify_hash(ont, name, hash_prefix)
    if sel.kind != SelectionKind.AXIOMS:
        raise SelectionKindError(
            name=name, expected="axioms", actual=sel.kind, operation="rm_axioms"
        )

    items = [
        r[0]
        for r in ont.conn.execute(
            "SELECT item FROM selection_items WHERE selection_name = ?", (name,)
        )
    ]

    removed: list[HashedAxiom] = []
    absent = 0
    with ont.conn:
        for h in items:
            row = ont.conn.execute(
                "SELECT hash, json(data) FROM axioms WHERE hash = ?", (h,)
            ).fetchone()
            if row is None:
                absent += 1
                continue
            full_hash, json_data = row
            axiom = load_axiom(json_data, f"axiom {full_hash[:8]} in remove_by_selection")
            _log_event(ont, "del", full_hash)
            ont.conn.execute("DELETE FROM axioms WHERE hash = ?", (full_hash,))
            removed.append(HashedAxiom(axiom=axiom, hash=full_hash))

    return removed, absent


def annotate(
    ont: Ontology,
    hash_prefix: str,
    *,
    add_annotations: list[Annotation] | None = None,
    remove_annotations: list[Annotation] | None = None,
) -> HashedAxiom:
    """Modify axiom-level metadata annotations. Accepts full hash or unambiguous prefix."""
    add_annotations = add_annotations or []
    remove_annotations = remove_annotations or []

    with ont.conn:
        rows = ont.conn.execute(
            "SELECT id, hash, json(data) FROM axioms WHERE hash LIKE ? || '%'",
            (hash_prefix,),
        ).fetchall()
        if not rows:
            raise AxiomNotFoundError(hash_prefix)
        if len(rows) > 1:
            samples = [r[1][:8] for r in rows]
            raise AmbiguousHashError(hash_prefix, len(rows), samples)

        axiom_id, full_hash, json_data = rows[0]
        axiom = load_axiom(json_data, f"axiom {full_hash[:8]} in annotate")

        current = list(axiom.annotations)
        for ann in remove_annotations:
            if ann in current:
                current.remove(ann)
        for ann in add_annotations:
            if ann not in current:
                current.append(ann)

        updated = axiom.model_copy(update={"annotations": tuple(current)})
        new_json = updated.model_dump_json()

        _log_event(ont, "del", full_hash)
        ont.conn.execute("UPDATE axioms SET data = jsonb(?) WHERE id = ?", (new_json, axiom_id))
        _log_event(ont, "add", full_hash, new_json)

        ont.conn.execute("DELETE FROM axiom_text WHERE axiom_id = ?", (axiom_id,))
        ont.conn.executemany(
            "INSERT INTO axiom_text (axiom_id, text, property) VALUES (?, ?, ?)",
            [
                (axiom_id, _extract_annotation_value(ann.value), str(ann.property))
                for ann in updated.annotations
            ],
        )

    return HashedAxiom(axiom=updated, hash=full_hash)


def _build_axiom_search(
    ont: Ontology,
    *,
    iri: IRI | None = None,
    axiom_types: list[str] | None = None,
    annotation_query: str | None = None,
    annotation_properties: list[str] | None = None,
    entity_query: str | None = None,
    within_selection: str | None = None,
) -> tuple[str, list[str | int]]:
    """Build the FROM...WHERE clause for axiom searches."""
    joins: list[str] = []
    conditions: list[str] = []
    params: list[str | int] = []

    if within_selection is not None:
        sel = selections.get_info(ont, within_selection)
        if sel.kind == SelectionKind.AXIOMS:
            joins.append(
                "JOIN selection_items si_w ON si_w.item = a.hash AND si_w.selection_name = ?"
            )
            params.append(within_selection)
        else:  # entities
            joins.append("JOIN axiom_entities ae_w ON ae_w.axiom_id = a.id")
            joins.append(
                "JOIN selection_items si_w ON si_w.item = ae_w.entity_iri AND si_w.selection_name = ?"
            )
            params.append(within_selection)

    if iri is not None:
        joins.append("JOIN axiom_entities ae ON ae.axiom_id = a.id")
        conditions.append("ae.entity_iri = ?")
        params.append(str(iri))

    if annotation_query is not None:
        joins.append("JOIN axiom_text at ON at.axiom_id = a.id")
        conditions.append("INSTR(at.text, ?) > 0")
        params.append(annotation_query)

    if annotation_properties:
        joins.append("JOIN entity_text et ON et.axiom_id = a.id")
        placeholders = ",".join("?" for _ in annotation_properties)
        conditions.append(f"et.property IN ({placeholders})")
        params.extend(annotation_properties)

    if entity_query is not None:
        joins.append("JOIN axiom_entities ae_eq ON ae_eq.axiom_id = a.id")
        conditions.append(
            "ae_eq.entity_iri IN ("
            "SELECT DISTINCT entity_iri FROM entity_text "
            "WHERE INSTR(LOWER(text), LOWER(?)) > 0"
            ")"
        )
        params.append(entity_query)

    if axiom_types:
        placeholders = ",".join("?" for _ in axiom_types)
        conditions.append(f"a.type IN ({placeholders})")
        params.extend(axiom_types)

    join_clause = (" " + " ".join(joins)) if joins else ""
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    base = f"FROM axioms a{join_clause}{where}"
    return base, params


def search(
    ont: Ontology,
    *,
    iri: IRI | None = None,
    axiom_types: list[str] | None = None,
    annotation_query: str | None = None,
    annotation_properties: list[str] | None = None,
    entity_query: str | None = None,
    within_selection: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchPage:
    """Paginated axiom search with optional filters.

    within_selection: scope to a named selection. Entity selection restricts to axioms
    mentioning those entities; axiom selection restricts to those specific axioms.
    """
    base, params = _build_axiom_search(
        ont,
        iri=iri,
        axiom_types=axiom_types,
        annotation_query=annotation_query,
        annotation_properties=annotation_properties,
        entity_query=entity_query,
        within_selection=within_selection,
    )

    total = ont.conn.execute(f"SELECT COUNT(DISTINCT a.id) {base}", params).fetchone()[0]

    axioms = [
        HashedAxiom(axiom=load_axiom(data, f"axiom {h[:8]} in search"), hash=h)
        for h, data in ont.conn.execute(
            f"SELECT DISTINCT a.hash, json(a.data) {base} ORDER BY a.id LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
    ]

    return SearchPage(axioms=axioms, total=total)


def collect_hashes(
    ont: Ontology,
    *,
    iri: IRI | None = None,
    axiom_types: list[str] | None = None,
    annotation_query: str | None = None,
    annotation_properties: list[str] | None = None,
    entity_query: str | None = None,
    within_selection: str | None = None,
) -> list[str]:
    """Return all matching axiom hashes (no data deserialization). For select workflows."""
    base, params = _build_axiom_search(
        ont,
        iri=iri,
        axiom_types=axiom_types,
        annotation_query=annotation_query,
        annotation_properties=annotation_properties,
        entity_query=entity_query,
        within_selection=within_selection,
    )
    return [r[0] for r in ont.conn.execute(f"SELECT DISTINCT a.hash {base}", params)]


def summary(ont: Ontology, *, within_selection: str | None = None) -> Counter[str]:
    if within_selection is None:
        return Counter(
            {
                r[0]: r[1]
                for r in ont.conn.execute("SELECT type, COUNT(*) FROM axioms GROUP BY type")
            }
        )
    sel = selections.get_info(ont, within_selection)
    if sel.kind == SelectionKind.AXIOMS:
        return Counter(
            {
                r[0]: r[1]
                for r in ont.conn.execute(
                    "SELECT a.type, COUNT(*) FROM axioms a "
                    "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
                    "GROUP BY a.type",
                    (within_selection,),
                )
            }
        )
    # entities: count axioms mentioning those entities
    return Counter(
        {
            r[0]: r[1]
            for r in ont.conn.execute(
                "SELECT a.type, COUNT(DISTINCT a.id) FROM axioms a "
                "JOIN axiom_entities ae ON ae.axiom_id = a.id "
                "JOIN selection_items si ON si.item = ae.entity_iri AND si.selection_name = ? "
                "GROUP BY a.type",
                (within_selection,),
            )
        }
    )
