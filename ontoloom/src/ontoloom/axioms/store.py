import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from ontoloom.axioms.types import (
    AddResult,
    AnnotateResult,
    AxiomSummary,
    RemoveBySelectionResult,
    RemoveResult,
    RenameResult,
    ReplaceResult,
)
from ontoloom.connection import Session
from ontoloom.entity_walker import iter_axiom_entities
from ontoloom.errors import InternalError, OntoloomError
from ontoloom.hashing import (
    AxiomHash,
    AxiomHashPrefix,
    HashedAxiom,
    disambiguating_prefixes,
    short_hash,
)
from ontoloom.load import load_axiom
from ontoloom.models import FrozenModel
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import AnnotationAssertion, BaseAxiom
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral, TypedLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes import check_iri_prefixes
from ontoloom.selections.store import (
    get_selection,
    require_locked_selection,
)
from ontoloom.selections.types import LockedSelection, SelectionKind, SelectionName
from ontoloom.text_index import LOCAL_NAME_PROPERTY
from ontoloom.utils import dedupe


class AxiomNotFoundError(OntoloomError):
    """No axiom matches the given hash prefix."""

    def __init__(self, prefix: AxiomHashPrefix):
        self.prefix = prefix
        super().__init__(f"No axiom matching hash prefix [{prefix}].")


class AmbiguousHashError(OntoloomError):
    """Hash prefix matches multiple axioms.

    `distinguishing_prefixes` are the minimum-length prefixes that uniquely
    identify each match -> the caller can copy any of them verbatim to retry.
    """

    def __init__(self, prefix: AxiomHashPrefix, count: int, distinguishing_prefixes: Sequence[str]):
        self.prefix = prefix
        self.count = count
        self.distinguishing_prefixes = distinguishing_prefixes
        max_shown = 10
        shown = ", ".join(distinguishing_prefixes[:max_shown])
        suffix = f", ... ({count - max_shown} more)" if count > max_shown else ""
        super().__init__(f"[{prefix}] matches {count} axioms: {shown}{suffix}.")


@dataclass(frozen=True, slots=True)
class ResolvedAxiom:
    axiom_id: int
    hash: AxiomHash
    json_data: str


def _resolve_unique_axiom(s: Session, prefix: AxiomHashPrefix) -> ResolvedAxiom:
    """Look up an axiom by hash prefix; raise on missing or ambiguous match."""
    rows = s._conn.execute(
        "SELECT id, hash, json(data) FROM axioms WHERE hash LIKE ? || '%'",
        (prefix,),
    ).fetchall()
    if not rows:
        raise AxiomNotFoundError(prefix)
    if len(rows) > 1:
        full_hashes = [r[1] for r in rows]
        raise AmbiguousHashError(prefix, len(rows), disambiguating_prefixes(full_hashes))
    return ResolvedAxiom(axiom_id=rows[0][0], hash=AxiomHash(rows[0][1]), json_data=rows[0][2])


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
    s._conn.execute(
        f"DELETE FROM axioms WHERE hash IN ({placeholders})",
        tuple(ha.hash for ha in axioms),
    )


def remove_by_hash(s: Session, hash_prefixes: Sequence[AxiomHashPrefix]) -> RemoveResult:
    to_remove: list[HashedAxiom] = []
    for prefix in hash_prefixes:
        resolved = _resolve_unique_axiom(s, prefix)
        axiom = load_axiom(
            resolved.json_data, f"axiom {short_hash(resolved.hash)} in remove_by_hash"
        )
        to_remove.append(HashedAxiom(axiom=axiom, hash=resolved.hash))

    _delete_axioms(s, to_remove)
    return RemoveResult(removed=tuple(to_remove))


def remove_by_selection(s: Session, within: LockedSelection) -> RemoveBySelectionResult:
    """Remove axioms referenced by an axiom selection. Best-effort: skips missing."""
    require_locked_selection(s, within, SelectionKind.AXIOMS, "remove_axioms")

    to_remove: list[HashedAxiom] = []
    absent = 0
    items = [
        r[0]
        for r in s._conn.execute(
            "SELECT item FROM selection_items WHERE selection_name = ?", (within.name,)
        )
    ]
    for h in items:
        row = s._conn.execute("SELECT hash, json(data) FROM axioms WHERE hash = ?", (h,)).fetchone()
        if row is None:
            absent += 1
            continue
        full_hash, json_data = row
        axiom = load_axiom(json_data, f"axiom {short_hash(full_hash)} in remove_by_selection")
        to_remove.append(HashedAxiom(axiom=axiom, hash=AxiomHash(full_hash)))

    _delete_axioms(s, to_remove)
    return RemoveBySelectionResult(removed=tuple(to_remove), absent=absent)


def annotate_axiom(
    s: Session,
    hash_prefix: AxiomHashPrefix,
    *,
    add_annotations: list[Annotation] | None = None,
    remove_annotations: list[Annotation] | None = None,
) -> AnnotateResult:
    """Modify axiom-level metadata annotations. Accepts full hash or unambiguous prefix.

    Returns an `AnnotateResult` with the actually-applied add/remove sets:
    duplicates against existing annotations are dropped from `added`, and
    removals targeting absent annotations are dropped from `removed` (so the
    counts reflect storage changes, not request size).
    """
    add_annotations = add_annotations or []
    remove_annotations = remove_annotations or []

    resolved = _resolve_unique_axiom(s, hash_prefix)
    axiom = load_axiom(resolved.json_data, f"axiom {short_hash(resolved.hash)} in annotate")

    current = list(axiom.annotations)
    for ann in remove_annotations:
        if ann in current:
            current.remove(ann)
    for ann in add_annotations:
        if ann not in current:
            current.append(ann)

    updated = axiom.model_copy(update={"annotations": tuple(current)})
    new_json = updated.model_dump_json()

    s._conn.execute("UPDATE axioms SET data = jsonb(?) WHERE id = ?", (new_json, resolved.axiom_id))

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


def replace_axiom(
    s: Session, old_hash_prefix: AxiomHashPrefix, new_axiom: BaseAxiom
) -> ReplaceResult:
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

    resolved = _resolve_unique_axiom(s, old_hash_prefix)
    old_axiom = load_axiom(resolved.json_data, f"axiom {short_hash(resolved.hash)} in replace")
    old_hashed = HashedAxiom(axiom=old_axiom, hash=resolved.hash)

    if new_h == resolved.hash:
        return ReplaceResult(old=old_hashed, new=old_hashed, was_noop=True)

    # Delete old, then attempt to insert new. If new_h collides with a
    # different existing axiom, INSERT OR IGNORE skips and that axiom keeps
    # its own annotations -> the carry-forward is irrelevant in that case.
    s._conn.execute("DELETE FROM axioms WHERE id = ?", (resolved.axiom_id,))
    new_axiom_id = insert_axiom(s, new_axiom)
    merged = new_axiom_id is None

    if not merged:
        # Carry old axiom-level annotations onto the new axiom; annotations
        # don't enter the canonical hash so new_h is unchanged.
        new_axiom = new_axiom.model_copy(update={"annotations": old_axiom.annotations})
        s._conn.execute(
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
    # cast is correct by construction: _sub returns the same shape it received,
    # and pyright can't model that without overloads for every input type.
    return cast("BaseAxiom", _sub(axiom, old_iri, new_iri))


def _sub(value: object, old_iri: IRI, new_iri: IRI):
    """Recursively rebuild `value`, replacing every IRI equal to `old_iri` with `new_iri`.

    Walks IRIs directly, tuples element-wise, and FrozenModel fields by name.
    Anything else is returned unchanged."""
    if isinstance(value, IRI):
        return new_iri if value == old_iri else value
    if isinstance(value, tuple):
        return tuple(_sub(v, old_iri, new_iri) for v in value)
    if isinstance(value, FrozenModel):
        updates = {}
        for name in type(value).model_fields:
            v = getattr(value, name)
            replaced = _sub(v, old_iri, new_iri)
            if replaced is not v:
                updates[name] = replaced
        return value.model_copy(update=updates) if updates else value
    return value


def rename_iri(
    s: Session,
    old_iri: IRI,
    new_iri: IRI,
    *,
    within: LockedSelection | None = None,
) -> RenameResult:
    """Replace old_iri with new_iri across all (or scoped) axioms. One batch_id.

    `within`: optional locked AXIOMS selection (`name@hash_prefix`) to restrict
    the rename. The hash prefix is verified against the current selection hash.

    Raises:
        StaleSelectionError: if `within.hash_prefix` does not match the current
            selection hash.
        SelectionKindError: if `within` is an entity selection; convert with
            `axioms_for` first.
    """
    check_iri_prefixes(s, [new_iri])
    batch = uuid.uuid4().hex[:12]
    results: list[ReplaceResult] = []

    if within is not None:
        require_locked_selection(s, within, SelectionKind.AXIOMS, "rename_iri")
        # ORDER BY a.hash: candidate iteration order determines event-log
        # insertion order; revert(n=1) replays the last batch in reverse.
        rows = s._conn.execute(
            "SELECT DISTINCT a.hash, json(a.data) FROM axioms a "
            "JOIN axiom_entities ae ON ae.axiom_id = a.id "
            "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
            "WHERE ae.entity_iri = ? ORDER BY a.hash",
            (within.name, old_iri),
        ).fetchall()
    else:
        rows = s._conn.execute(
            "SELECT DISTINCT a.hash, json(a.data) FROM axioms a "
            "JOIN axiom_entities ae ON ae.axiom_id = a.id "
            "WHERE ae.entity_iri = ? ORDER BY a.hash",
            (old_iri,),
        ).fetchall()

    for old_full_hash, old_json_data in rows:
        old_axiom = load_axiom(old_json_data, f"rename {old_iri} -> {new_iri}")
        new_axiom = _substitute_iri(old_axiom, old_iri, new_iri)
        new_h = HashedAxiom.of(new_axiom).hash
        old_hashed = HashedAxiom(axiom=old_axiom, hash=old_full_hash)
        new_hashed = HashedAxiom(axiom=new_axiom, hash=new_h)

        if new_h == old_full_hash:
            results.append(ReplaceResult(old=old_hashed, new=old_hashed, was_noop=True))
            continue

        s._conn.execute("DELETE FROM axioms WHERE hash = ?", (old_full_hash,))
        merged = insert_axiom(s, new_axiom) is None

        results.append(
            ReplaceResult(
                old=old_hashed,
                new=new_hashed,
                was_noop=False,
                was_merged_into_existing=merged,
            )
        )

    return RenameResult(old_iri=old_iri, new_iri=new_iri, replaced=tuple(results), batch_id=batch)


def _count_axioms_by_type(s: Session, query: str, params: Sequence[object] = ()):
    return Counter(dict(s._conn.execute(query, params)))


def axiom_summary(s: Session, *, within: SelectionName | None = None) -> AxiomSummary:
    if within is None:
        by_type = _count_axioms_by_type(s, "SELECT type, COUNT(*) FROM axioms GROUP BY type")
    else:
        sel = get_selection(s, within)
        if sel.kind == SelectionKind.AXIOMS:
            by_type = _count_axioms_by_type(
                s,
                "SELECT a.type, COUNT(*) FROM axioms a "
                "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
                "GROUP BY a.type",
                (within,),
            )
        else:  # entities: count axioms mentioning those entities
            by_type = _count_axioms_by_type(
                s,
                "SELECT a.type, COUNT(DISTINCT a.id) FROM axioms a "
                "JOIN axiom_entities ae ON ae.axiom_id = a.id "
                "JOIN selection_items si ON si.item = ae.entity_iri "
                "AND si.selection_name = ? GROUP BY a.type",
                (within,),
            )
    return AxiomSummary(total=sum(by_type.values()), by_type=by_type)


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
    cursor = s._conn.execute(
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
    s._conn.execute("DELETE FROM axiom_text WHERE axiom_id = ?", (axiom_id,))
    rows = [
        (axiom_id, _annotation_value_to_text(ann.value), str(ann.property)) for ann in annotations
    ]
    if rows:
        s._conn.executemany(
            "INSERT INTO axiom_text (axiom_id, text, property) VALUES (?, ?, ?)",
            rows,
        )


def _populate_indexes(s: Session, axiom: BaseAxiom, axiom_id: int):
    """Populate axiom_entities, entity_text, and axiom_text for a newly inserted axiom."""
    # Walk entities once: each yielded (iri, role, position) emits an
    # axiom_entities row, and the first occurrence of each iri also emits an
    # entity_text row keyed by local-name (used for IRI-based search).
    entity_rows = []
    text_rows = []
    seen_iris: set[str] = set()

    for iri, role, position in iter_axiom_entities(axiom):
        iri_str = str(iri)
        role_val = role.value if isinstance(role, EntityType) else role
        pos_val = position.value if position is not None else None
        entity_rows.append((axiom_id, iri_str, role_val, pos_val))
        if iri_str not in seen_iris:
            seen_iris.add(iri_str)
            text_rows.append((axiom_id, iri_str, iri.local_name, LOCAL_NAME_PROPERTY))

    # AnnotationAssertion adds one extra entity_text row indexing the value
    # under the annotation property (e.g. rdfs:label -> "Dog"), enabling
    # property-scoped text search.
    if isinstance(axiom, AnnotationAssertion):
        text_rows.append(
            (
                axiom_id,
                str(axiom.subject),
                _annotation_value_to_text(axiom.value),
                str(axiom.property),
            )
        )

    s._conn.executemany(
        "INSERT INTO axiom_entities (axiom_id, entity_iri, role, position) VALUES (?, ?, ?, ?)",
        entity_rows,
    )
    s._conn.executemany(
        "INSERT INTO entity_text (axiom_id, entity_iri, text, property) VALUES (?, ?, ?, ?)",
        text_rows,
    )

    # axiom_text holds the axiom-level metadata annotations (separate from
    # entity-level entity_text); FTS over this powers `match_axioms` searches
    # by annotation content.
    axiom_text_rows = [
        (axiom_id, _annotation_value_to_text(ann.value), str(ann.property))
        for ann in axiom.annotations
    ]
    if axiom_text_rows:
        s._conn.executemany(
            "INSERT INTO axiom_text (axiom_id, text, property) VALUES (?, ?, ?)",
            axiom_text_rows,
        )
