import json
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
from ontoloom.ontology.models.literals import IRI, Annotation, FrozenModel
from ontoloom.ontology.types import (
    AddResult,
    HashedAxiom,
    LockedSelection,
    RemoveResult,
    RenameResult,
    ReplaceResult,
    SelectionKind,
)

_HEX_RE = re.compile(r"^[0-9a-f]+$")


def _log_event(
    ont: Ontology,
    op: str,
    axiom_hash: str,
    axiom_json: str | None = None,
    *,
    replaces_hash: str | None = None,
    annotation_diff: str | None = None,
    batch_id: str | None = None,
):
    ont.conn.execute(
        "INSERT INTO events (session_id, op, axiom_hash, axiom_json, replaces_hash, annotation_diff, batch_id)"
        " VALUES (?, ?, ?, jsonb(?), ?, ?, ?)",
        (ont.session_id, op, axiom_hash, axiom_json, replaces_hash, annotation_diff, batch_id),
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
            _log_event(ont, "del", ha.hash, ha.axiom.model_dump_json())
            ont.conn.execute("DELETE FROM axioms WHERE hash = ?", (ha.hash,))

    return RemoveResult(removed=to_remove)


def remove_by_selection(ont: Ontology, within: LockedSelection) -> tuple[list[HashedAxiom], int]:
    """Remove axioms referenced by an axiom selection. Best-effort: skips missing."""
    sel = selections.verify_hash(ont, within.name, within.hash_prefix)
    if sel.kind != SelectionKind.AXIOMS:
        raise SelectionKindError(
            name=within.name, expected="axioms", actual=sel.kind, operation="rm_axioms"
        )

    removed: list[HashedAxiom] = []
    absent = 0
    with ont.conn:
        items = [
            r[0]
            for r in ont.conn.execute(
                "SELECT item FROM selection_items WHERE selection_name = ?", (within.name,)
            )
        ]
        for h in items:
            row = ont.conn.execute(
                "SELECT hash, json(data) FROM axioms WHERE hash = ?", (h,)
            ).fetchone()
            if row is None:
                absent += 1
                continue
            full_hash, json_data = row
            axiom = load_axiom(json_data, f"axiom {full_hash[:8]} in remove_by_selection")
            _log_event(ont, "del", full_hash, json_data)
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

        ont.conn.execute("UPDATE axioms SET data = jsonb(?) WHERE id = ?", (new_json, axiom_id))

        original = set(axiom.annotations)
        final = set(current)
        actually_added = [a.model_dump() for a in final - original]
        actually_removed = [a.model_dump() for a in original - final]
        if actually_added or actually_removed:
            diff = json.dumps({"added": actually_added, "removed": actually_removed})
            _log_event(ont, "annotate", full_hash, annotation_diff=diff)

        ont.conn.execute("DELETE FROM axiom_text WHERE axiom_id = ?", (axiom_id,))
        ont.conn.executemany(
            "INSERT INTO axiom_text (axiom_id, text, property) VALUES (?, ?, ?)",
            [
                (axiom_id, _extract_annotation_value(ann.value), str(ann.property))
                for ann in updated.annotations
            ],
        )

    return HashedAxiom(axiom=updated, hash=full_hash)


def replace(ont: Ontology, old_hash_prefix: str, new_axiom: Axiom) -> ReplaceResult:
    """Atomic delete+add with event tracking.

    Old axiom-level annotations are carried forward onto the new axiom — annotations
    are excluded from the canonical hash, so the new hash is unaffected. Any
    annotations on the input `new_axiom` are discarded; use `annotate` to modify
    annotations afterwards.

    No-op if new content hashes to the same value as old.
    If new hash matches a different existing axiom: old is deleted, add is skipped
    (the existing axiom keeps its own annotations), event records the mapping.
    """
    if not _HEX_RE.match(old_hash_prefix):
        raise InvalidHashError(old_hash_prefix)

    new_h = axiom_hash(new_axiom)

    with ont.conn:
        rows = ont.conn.execute(
            "SELECT id, hash, json(data) FROM axioms WHERE hash LIKE ? || '%'",
            (old_hash_prefix,),
        ).fetchall()
        if not rows:
            raise AxiomNotFoundError(old_hash_prefix)
        if len(rows) > 1:
            samples = [r[1][:8] for r in rows]
            raise AmbiguousHashError(old_hash_prefix, len(rows), samples)

        old_id, old_full_hash, old_json = rows[0]

        if new_h == old_full_hash:
            return ReplaceResult(old_hash=old_full_hash, new_hash=new_h, was_noop=True)

        # Carry old axiom-level annotations onto the new axiom; annotations don't
        # enter the canonical hash so new_h is unchanged.
        old_axiom = load_axiom(old_json, f"axiom {old_full_hash[:8]} in replace")
        new_axiom = new_axiom.model_copy(update={"annotations": old_axiom.annotations})
        new_json = new_axiom.model_dump_json()

        # Delete old
        ont.conn.execute("DELETE FROM axioms WHERE id = ?", (old_id,))

        # Add new (idempotent — may already exist)
        cursor = ont.conn.execute(
            "INSERT OR IGNORE INTO axioms (hash, type, data) VALUES (?, ?, jsonb(?))",
            (new_h, new_axiom.type, new_json),
        )
        if cursor.rowcount > 0:
            new_id = cursor.lastrowid
            if new_id is None:
                msg = "INSERT succeeded but lastrowid is None"
                raise RuntimeError(msg)
            populate(ont, new_axiom, new_id)

        _log_event(
            ont,
            "replace",
            new_h,
            new_json,
            replaces_hash=old_full_hash,
        )

    return ReplaceResult(old_hash=old_full_hash, new_hash=new_h, was_noop=False)


def _substitute_iri(value, old_iri: str, new_iri: str):
    """Walk a model value tree, replacing each IRI == old_iri with new_iri.

    Only IRI-typed fields are substituted; plain str fields (e.g. LangLiteral.value,
    TypedLiteral.value) are left unchanged even if they coincidentally equal old_iri.
    """
    if isinstance(value, IRI):
        return IRI(new_iri) if value == old_iri else value
    if isinstance(value, tuple):
        return tuple(_substitute_iri(v, old_iri, new_iri) for v in value)
    if isinstance(value, FrozenModel):
        updates = {}
        for name in type(value).model_fields:
            v = getattr(value, name)
            replaced = _substitute_iri(v, old_iri, new_iri)
            if replaced is not v:
                updates[name] = replaced
        return value.model_copy(update=updates) if updates else value
    return value


def rename_iri(
    ont: Ontology,
    old_iri: str,
    new_iri: str,
    *,
    within: LockedSelection | None = None,
) -> RenameResult:
    """Replace old_iri with new_iri across all (or scoped) axioms. One batch_id.

    `within`: optional locked AXIOMS selection (`name@hash_prefix`) to restrict the
    rename. The hash prefix is verified against the current selection hash —
    raises StaleSelectionError on mismatch. Raises SelectionKindError if the
    selection is an entity selection; convert with `axioms_for` first.
    """
    import uuid

    batch = uuid.uuid4().hex[:12]
    results: list[ReplaceResult] = []

    with ont.conn:
        # Candidate reads are inside the transaction to avoid TOCTOU.
        if within is not None:
            sel = selections.verify_hash(ont, within.name, within.hash_prefix)
            if sel.kind != SelectionKind.AXIOMS:
                raise SelectionKindError(
                    name=within.name,
                    expected="axioms",
                    actual=sel.kind,
                    operation="rename_iri",
                )
            rows = ont.conn.execute(
                "SELECT DISTINCT a.hash, json(a.data) FROM axioms a "
                "JOIN axiom_entities ae ON ae.axiom_id = a.id "
                "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
                "WHERE ae.entity_iri = ?",
                (within.name, old_iri),
            ).fetchall()
        else:
            rows = ont.conn.execute(
                "SELECT DISTINCT a.hash, json(a.data) FROM axioms a "
                "JOIN axiom_entities ae ON ae.axiom_id = a.id "
                "WHERE ae.entity_iri = ?",
                (old_iri,),
            ).fetchall()

        for old_full_hash, old_json_data in rows:
            old_axiom = load_axiom(old_json_data, f"rename {old_iri} -> {new_iri}")
            new_axiom = _substitute_iri(old_axiom, old_iri, new_iri)
            new_h = axiom_hash(new_axiom)
            new_json = new_axiom.model_dump_json()

            if new_h == old_full_hash:
                results.append(ReplaceResult(old_hash=old_full_hash, new_hash=new_h, was_noop=True))
                continue

            ont.conn.execute("DELETE FROM axioms WHERE hash = ?", (old_full_hash,))

            cursor = ont.conn.execute(
                "INSERT OR IGNORE INTO axioms (hash, type, data) VALUES (?, ?, jsonb(?))",
                (new_h, new_axiom.type, new_json),
            )
            if cursor.rowcount > 0:
                new_id = cursor.lastrowid
                if new_id is None:
                    msg = "INSERT succeeded but lastrowid is None"
                    raise RuntimeError(msg)
                populate(ont, new_axiom, new_id)

            _log_event(
                ont,
                "replace",
                new_h,
                new_json,
                replaces_hash=old_full_hash,
                batch_id=batch,
            )
            results.append(ReplaceResult(old_hash=old_full_hash, new_hash=new_h, was_noop=False))

    return RenameResult(old_iri=old_iri, new_iri=new_iri, replaced=results, batch_id=batch)


def summary(ont: Ontology, *, within: str | None = None) -> Counter[str]:
    if within is None:
        return Counter(
            {
                r[0]: r[1]
                for r in ont.conn.execute("SELECT type, COUNT(*) FROM axioms GROUP BY type")
            }
        )
    sel = selections.get_info(ont, within)
    if sel.kind == SelectionKind.AXIOMS:
        return Counter(
            {
                r[0]: r[1]
                for r in ont.conn.execute(
                    "SELECT a.type, COUNT(*) FROM axioms a "
                    "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
                    "GROUP BY a.type",
                    (within,),
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
                (within,),
            )
        }
    )
