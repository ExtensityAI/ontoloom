from collections.abc import Sequence
from typing import cast

from ontoloom.axioms.deserialize import load_axiom
from ontoloom.axioms.entity_walker import iter_axiom_entities
from ontoloom.axioms.hashing import AxiomHash, AxiomNotFoundError, load_axiom_row, short_hash
from ontoloom.axioms.types import (
    AddResult,
    AnnotateResult,
    HashedAxiom,
    RemoveBySelectionResult,
    RemoveResult,
    RenameResult,
    ReplaceResult,
)
from ontoloom.connection import Session
from ontoloom.entities.text import record_annotation_value, record_local_name
from ontoloom.errors import InternalError, StoreCorruptionError
from ontoloom.models import FrozenModel
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import BaseAxiom
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral, TypedLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes.store import check_iri_prefixes
from ontoloom.query.constraints import AxiomConstraint, InAxiomSelection, MentionsAll
from ontoloom.query.dispatch import execute
from ontoloom.query.list_axioms import ListAxioms
from ontoloom.selections.store import get_axiom_selection
from ontoloom.selections.types import SelectionName
from ontoloom.utils import dedupe


def add_axioms(s: Session, axioms: Sequence[BaseAxiom]) -> AddResult:
    check_iri_prefixes(s, (iri for axiom in axioms for iri, _, _ in iter_axiom_entities(axiom)))
    added: list[HashedAxiom] = []
    skipped: list[HashedAxiom] = []

    for axiom in axioms:
        ha = HashedAxiom.of(axiom)
        if insert_axiom(s, axiom) is None:
            skipped.append(ha)
            continue
        added.append(ha)

    return AddResult(added=tuple(added), skipped=tuple(skipped))


def _delete_axioms(s: Session, axioms: Sequence[HashedAxiom]):
    """Delete the given axiom rows in one batch."""
    if not axioms:
        return
    placeholders = ",".join("?" for _ in axioms)
    s.conn.execute(
        f"DELETE FROM axioms WHERE hash IN ({placeholders})",
        tuple(ha.hash for ha in axioms),
    )


def remove_by_hash(s: Session, hashes: Sequence[AxiomHash]) -> RemoveResult:
    if not hashes:
        return RemoveResult(removed=())

    placeholders = ",".join("?" for _ in hashes)
    found: dict[AxiomHash, str] = {
        AxiomHash(h): data
        for h, data in s.conn.execute(
            f"SELECT hash, json(data) FROM axioms WHERE hash IN ({placeholders})",
            tuple(hashes),
        )
    }
    for h in hashes:
        if h not in found:
            raise AxiomNotFoundError(h)

    to_remove: list[HashedAxiom] = []
    for h in hashes:
        try:
            axiom = load_axiom(found[h])
        except StoreCorruptionError as e:
            msg = f"axiom {short_hash(h)} in remove_by_hash"
            raise StoreCorruptionError(msg, e.original) from e
        to_remove.append(HashedAxiom(axiom=axiom, hash=h))

    _delete_axioms(s, to_remove)
    return RemoveResult(removed=tuple(to_remove))


def remove_by_selection(s: Session, within: SelectionName) -> RemoveBySelectionResult:
    """Remove axioms referenced by an axiom selection. Best-effort: skips missing.

    The post-mutation `AxiomSelection` is returned so adapters (MCP) can render
    a fresh ref for follow-up calls.
    """
    to_remove: list[HashedAxiom] = []
    absent = 0
    rows = s.conn.execute(
        "SELECT si.item, a.hash, json(a.data) "
        "FROM axiom_selection_items si LEFT JOIN axioms a ON a.hash = si.item "
        "WHERE si.selection_name = ?",
        (within,),
    )
    for _item, full_hash, json_data in rows:
        if full_hash is None:
            absent += 1
            continue
        try:
            axiom = load_axiom(json_data)
        except StoreCorruptionError as e:
            msg = f"axiom {short_hash(full_hash)} in remove_by_selection"
            raise StoreCorruptionError(msg, e.original) from e
        to_remove.append(HashedAxiom(axiom=axiom, hash=AxiomHash(full_hash)))

    _delete_axioms(s, to_remove)
    meta = get_axiom_selection(s, within)
    return RemoveBySelectionResult(removed=tuple(to_remove), absent=absent, meta=meta)


def annotate_axiom(
    s: Session,
    axiom_hash: AxiomHash,
    *,
    add_annotations: Sequence[Annotation] = (),
    remove_annotations: Sequence[Annotation] = (),
) -> AnnotateResult:
    """Modify axiom-level metadata annotations.

    Returns an `AnnotateResult` with the actually-applied add/remove sets:
    duplicates against existing annotations are dropped from `added`, and
    removals targeting absent annotations are dropped from `removed` (so the
    counts reflect storage changes, not request size).
    """
    resolved = load_axiom_row(s, axiom_hash)
    try:
        axiom = load_axiom(resolved.json_data)
    except StoreCorruptionError as e:
        msg = f"axiom {short_hash(resolved.hash)} in annotate"
        raise StoreCorruptionError(msg, e.original) from e

    current = list(axiom.annotations)
    for ann in remove_annotations:
        if ann in current:
            current.remove(ann)
    for ann in add_annotations:
        if ann not in current:
            current.append(ann)

    updated = axiom.model_copy(update={"annotations": tuple(current)})
    new_json = updated.model_dump_json()

    s.conn.execute("UPDATE axioms SET data = jsonb(?) WHERE id = ?", (new_json, resolved.axiom_id))

    original = set(axiom.annotations)
    final = set(current)
    new_added = final - original
    new_removed = original - final
    applied_added = tuple(a for a in dedupe(add_annotations) if a in new_added)
    applied_removed = tuple(a for a in dedupe(remove_annotations) if a in new_removed)

    repopulate_axiom_text(s, resolved.axiom_id, updated.annotations)

    return AnnotateResult(
        hashed=HashedAxiom(axiom=updated, hash=resolved.hash),
        added=applied_added,
        removed=applied_removed,
    )


def replace_axiom(s: Session, old_hash: AxiomHash, new_axiom: BaseAxiom) -> ReplaceResult:
    """Atomic delete+add with event tracking.

    Old axiom-level annotations are carried forward onto the new axiom -> annotations
    are excluded from the canonical hash, so the new hash is unaffected. Any
    annotations on the input `new_axiom` are discarded; use `annotate` to modify
    annotations afterwards.

    No-op if new content hashes to the same value as old.
    If new hash matches a different existing axiom: old is deleted, add is skipped
    (the existing axiom keeps its own annotations), event records the mapping.
    """
    check_iri_prefixes(s, (iri for iri, _, _ in iter_axiom_entities(new_axiom)))

    new_h = HashedAxiom.of(new_axiom).hash

    resolved = load_axiom_row(s, old_hash)
    try:
        old_axiom = load_axiom(resolved.json_data)
    except StoreCorruptionError as e:
        msg = f"axiom {short_hash(resolved.hash)} in replace"
        raise StoreCorruptionError(msg, e.original) from e
    old_hashed = HashedAxiom(axiom=old_axiom, hash=resolved.hash)

    if new_h == resolved.hash:
        return ReplaceResult(old=old_hashed, new=old_hashed, was_noop=True)

    # Delete old, then attempt to insert new. If new_h collides with a
    # different existing axiom, INSERT OR IGNORE skips and that axiom keeps
    # its own annotations -> the carry-forward is irrelevant in that case.
    s.conn.execute("DELETE FROM axioms WHERE id = ?", (resolved.axiom_id,))
    new_axiom_id = insert_axiom(s, new_axiom)
    merged = new_axiom_id is None

    if not merged:
        # Carry old axiom-level annotations onto the new axiom; annotations
        # don't enter the canonical hash so new_h is unchanged.
        new_axiom = new_axiom.model_copy(update={"annotations": old_axiom.annotations})
        s.conn.execute(
            "UPDATE axioms SET data = jsonb(?) WHERE id = ?",
            (new_axiom.model_dump_json(), new_axiom_id),
        )
        repopulate_axiom_text(s, new_axiom_id, new_axiom.annotations)

    return ReplaceResult(
        old=old_hashed,
        new=HashedAxiom(axiom=new_axiom, hash=new_h),
        was_noop=False,
        was_merged_into_existing=merged,
    )


def _substitute_iri(axiom: BaseAxiom, old_iri: IRI, new_iri: IRI) -> BaseAxiom:
    """Walk axiom, replacing each IRI == old_iri with new_iri.

    Only IRI-typed fields are substituted; plain str fields (e.g. LangLiteral.value,
    TypedLiteral.value) are left unchanged even if they coincidentally equal old_iri.
    """
    # cast is correct by construction: _substitute_value returns the same shape it
    # received, and pyright can't model that without overloads for every input type.
    return cast("BaseAxiom", _substitute_value(axiom, old_iri, new_iri))


def _substitute_value(value: object, old_iri: IRI, new_iri: IRI):
    """Recursively rebuild `value`, replacing every IRI equal to `old_iri` with `new_iri`.

    Walks IRIs directly, tuples element-wise, and FrozenModel fields by name.
    Anything else is returned unchanged."""
    if isinstance(value, IRI):
        return new_iri if value == old_iri else value
    if isinstance(value, tuple):
        return tuple(_substitute_value(v, old_iri, new_iri) for v in value)
    if isinstance(value, FrozenModel):
        updates = {}
        for name in type(value).model_fields:
            v = getattr(value, name)
            replaced = _substitute_value(v, old_iri, new_iri)
            if replaced is not v:
                updates[name] = replaced
        return value.model_copy(update=updates) if updates else value
    return value


def rename_iri(
    s: Session,
    old_iri: IRI,
    new_iri: IRI,
    *,
    within: SelectionName | None = None,
) -> RenameResult:
    """Replace old_iri with new_iri across all (or scoped) axioms.

    `within`: optional axiom selection to restrict the rename. The kind is
    enforced by the parameter type.
    """
    check_iri_prefixes(s, [new_iri])
    results: list[ReplaceResult] = []

    constraints: list[AxiomConstraint] = [MentionsAll(iris=(old_iri,))]
    if within is not None:
        constraints.append(InAxiomSelection(name=within))

    rows = list(execute(s, ListAxioms(constraints=tuple(constraints))))

    for old_full_hash, old_json_data in rows:
        try:
            old_axiom = load_axiom(old_json_data)
        except StoreCorruptionError as e:
            msg = f"rename {old_iri} -> {new_iri}"
            raise StoreCorruptionError(msg, e.original) from e
        new_axiom = _substitute_iri(old_axiom, old_iri, new_iri)
        new_h = HashedAxiom.of(new_axiom).hash
        old_hashed = HashedAxiom(axiom=old_axiom, hash=old_full_hash)
        new_hashed = HashedAxiom(axiom=new_axiom, hash=new_h)

        if new_h == old_full_hash:
            results.append(ReplaceResult(old=old_hashed, new=old_hashed, was_noop=True))
            continue

        s.conn.execute("DELETE FROM axioms WHERE hash = ?", (old_full_hash,))
        merged = insert_axiom(s, new_axiom) is None

        results.append(
            ReplaceResult(
                old=old_hashed,
                new=new_hashed,
                was_noop=False,
                was_merged_into_existing=merged,
            )
        )

    return RenameResult(old_iri=old_iri, new_iri=new_iri, replaced=tuple(results))


def _annotation_value_to_text(value: IRI | TypedLiteral | LangLiteral):
    """Flatten an annotation value to a single string for the text index."""
    if isinstance(value, IRI):
        return str(value)
    return value.value


def insert_axiom(s: Session, axiom: BaseAxiom) -> int | None:
    """INSERT OR IGNORE axiom row and populate indexes.

    Returns the new axiom_id, or None if an axiom with the same hash already
    existed (same hash = same axiom, so INSERT OR IGNORE is always safe).
    """
    h = HashedAxiom.of(axiom).hash
    json_data = axiom.model_dump_json()
    cursor = s.conn.execute(
        "INSERT OR IGNORE INTO axioms (hash, type, data) VALUES (?, ?, jsonb(?))",
        (h, axiom.tag(), json_data),
    )
    if cursor.rowcount == 0:
        return None

    axiom_id = cursor.lastrowid
    if axiom_id is None:
        msg = "INSERT succeeded but lastrowid is None"
        raise InternalError(msg)
    _populate_indexes(s, axiom, axiom_id)
    return axiom_id


def repopulate_axiom_text(s: Session, axiom_id: int, annotations: tuple[Annotation, ...]) -> None:
    """Rebuild axiom_text index rows for a single axiom after an annotation change."""
    s.conn.execute("DELETE FROM axiom_text WHERE axiom_id = ?", (axiom_id,))
    rows = [
        (axiom_id, _annotation_value_to_text(ann.value), str(ann.property)) for ann in annotations
    ]
    if rows:
        s.conn.executemany(
            "INSERT INTO axiom_text (axiom_id, text, property) VALUES (?, ?, ?)",
            rows,
        )


def _populate_indexes(s: Session, axiom: BaseAxiom, axiom_id: int):
    """Populate axiom_entities, entity_text, and axiom_text for a newly inserted axiom."""
    # Walk entities once: each yielded (iri, role, position) emits an
    # axiom_entities row, and the first occurrence of each iri delegates the
    # entity_text local_name row to the entities/text writer.
    entity_rows = []
    seen_iris: set[str] = set()

    for iri, role, position in iter_axiom_entities(axiom):
        iri_str = str(iri)
        role_val = role.value if isinstance(role, EntityType) else role
        pos_val = position.value if position is not None else None
        entity_rows.append((axiom_id, iri_str, role_val, pos_val))
        if iri_str not in seen_iris:
            seen_iris.add(iri_str)
            record_local_name(s, axiom_id, iri)

    record_annotation_value(s, axiom_id, axiom)

    s.conn.executemany(
        "INSERT INTO axiom_entities (axiom_id, entity_iri, role, position) VALUES (?, ?, ?, ?)",
        entity_rows,
    )

    # axiom_text indexes axiom-level annotation values, keyed by axiom id and
    # annotation property. Powers `find_axioms`.
    axiom_text_rows = [
        (axiom_id, _annotation_value_to_text(ann.value), str(ann.property))
        for ann in axiom.annotations
    ]
    if axiom_text_rows:
        s.conn.executemany(
            "INSERT INTO axiom_text (axiom_id, text, property) VALUES (?, ?, ?)",
            axiom_text_rows,
        )
