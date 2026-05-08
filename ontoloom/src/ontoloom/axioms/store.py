import json
import re
import uuid
from collections import Counter
from collections.abc import Sequence
from typing import cast

from ontoloom.axioms.types import (
    AddResult,
    AxiomSummary,
    RemoveBySelectionResult,
    RemoveResult,
    RenameResult,
    ReplaceResult,
)
from ontoloom.connection import Session
from ontoloom.entity_walker import iter_axiom_entities
from ontoloom.errors import InternalError, OntoloomError
from ontoloom.hashing import HASH_DISPLAY_LEN, HashedAxiom, disambiguating_prefixes
from ontoloom.load import load_axiom
from ontoloom.models import FrozenModel
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import AnnotationAssertion, BaseAxiom
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral, TypedLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.selections.store import (
    SelectionKindError,
    get_selection,
    verify_selection_hash,
)
from ontoloom.selections.types import LockedSelection, SelectionKind


class AxiomNotFoundError(OntoloomError):
    """No axiom matches the given hash prefix."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        super().__init__(f"No axiom matching hash prefix [{prefix}].")


class AmbiguousHashError(OntoloomError):
    """Hash prefix matches multiple axioms.

    `distinguishing_prefixes` are the minimum-length prefixes that uniquely
    identify each match -> the caller can copy any of them verbatim to retry.
    """

    def __init__(self, prefix: str, count: int, distinguishing_prefixes: Sequence[str]):
        self.prefix = prefix
        self.count = count
        self.distinguishing_prefixes = distinguishing_prefixes
        max_shown = 10
        shown = ", ".join(distinguishing_prefixes[:max_shown])
        suffix = f", ... ({count - max_shown} more)" if count > max_shown else ""
        super().__init__(f"[{prefix}] matches {count} axioms: {shown}{suffix}.")


class InvalidHashError(OntoloomError):
    """Hash prefix contains non-hex characters."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        super().__init__(f"[{prefix}] is not a valid hex hash prefix.")


_HEX_RE = re.compile(r"^[0-9a-f]+$")


def is_valid_hex(s: str):
    # A: is a general utility function, shoudl be moved somewhere better. no need for this complex explanation
    # A global: docs only explain what a func does. also, should be concise. e.g. this does not even need a comment, it is entirely clear what it does. the explanation for what it is used should rather be moved to the actual use location, it has nothing to do with what this function does. make this also a general python principle (like in your python rules or wherever, just like that other one on spacing)
    """True if `s` is a non-empty lowercase hex string. Use to validate hash prefixes
    before they reach SQL -> guarantees no LIKE metacharacters can appear."""
    return _HEX_RE.match(s) is not None


def _resolve_unique_axiom(s: Session, prefix: str) -> tuple[int, str, str]:
    """Look up an axiom by hash prefix; raise on missing or ambiguous match. Returns (id, full_hash, json_data)."""
    if not is_valid_hex(prefix):
        raise InvalidHashError(prefix)
    rows = s.conn.execute(
        "SELECT id, hash, json(data) FROM axioms WHERE hash LIKE ? || '%'",
        (prefix,),
    ).fetchall()
    if not rows:
        raise AxiomNotFoundError(prefix)
    if len(rows) > 1:
        full_hashes = [r[1] for r in rows]
        raise AmbiguousHashError(prefix, len(rows), disambiguating_prefixes(full_hashes))
    return rows[0]  # A: returns raw row, very bad, why?


def _log_event(
    # A: why is this not in history? also, I feel like we need multiple funcs to log events, just like we would have multiple event types? these optional args are hard to get right, so make multiple funcs, and why do we take both hash and json? just take the obj, we even have HashedAxiom
    s: Session,
    op: str,
    axiom_hash: str,
    axiom_json: str | None = None,
    *,
    replaces_hash: str | None = None,
    annotation_diff: str | None = None,
    batch_id: str | None = None,
):
    s.conn.execute(
        "INSERT INTO events (session_id, op, axiom_hash, axiom_json, replaces_hash, annotation_diff, batch_id)"
        " VALUES (?, ?, ?, jsonb(?), ?, ?, ?)",
        (s.session_id, op, axiom_hash, axiom_json, replaces_hash, annotation_diff, batch_id),
    )


def add_axioms(s: Session, axioms: Sequence[BaseAxiom]) -> AddResult:
    added: list[HashedAxiom] = []
    skipped: list[HashedAxiom] = []

    for axiom in axioms:
        h = HashedAxiom.of(axiom).hash  # inline into ha creation
        json_data = (
            axiom.model_dump_json()
        )  # A: should be computed where actually needed, this is noise here
        ha = HashedAxiom(axiom=axiom, hash=h)
        if insert_axiom(s, axiom, ignore_existing=True) is None:
            skipped.append(ha)
            continue
        added.append(ha)
        _log_event(s, "add", h, json_data)

    return AddResult(added=tuple(added), skipped=tuple(skipped))


def remove_axioms_by_hash(s: Session, hash_prefixes: list[str]) -> RemoveResult:
    # A: name is bad, remove_by_hashes, but then again, I am not sure whether removal by hash prefixes should be done here! is this not a MCP concern? this would also apply to search, so it is not as easy, because if we only allow remove of Axiom instances here, then search would also not allow prefixes? or could it still? what do you think?
    for prefix in hash_prefixes:
        if not is_valid_hex(prefix):
            raise InvalidHashError(prefix)

    to_remove: list[HashedAxiom] = []
    for prefix in hash_prefixes:
        _, full_hash, json_data = _resolve_unique_axiom(s, prefix)
        axiom = load_axiom(json_data, f"axiom {full_hash[:HASH_DISPLAY_LEN]} in remove_by_hash")
        to_remove.append(HashedAxiom(axiom=axiom, hash=full_hash))

    for ha in to_remove:
        # A: again, unclean because of events, already discussed in detail
        _log_event(s, "del", ha.hash, ha.axiom.model_dump_json())
        s.conn.execute("DELETE FROM axioms WHERE hash = ?", (ha.hash,))

    return RemoveResult(removed=tuple(to_remove))


def remove_axioms_by_selection(s: Session, within: LockedSelection) -> RemoveBySelectionResult:
    # A: I feel like this function should resolve axioms, then use remove_axioms as mentioned above (not with prefix. at least if we keep the remove by prefix, then make a authoritative remove_axioms func s.t. remove by prefix first resolves then calls that, same as this one. saves us a lot of code and ugliness.) might even unify results? or if not, compose or inherit RemoveResult in RemoveBySelectionResult or sth
    """Remove axioms referenced by an axiom selection. Best-effort: skips missing."""
    sel = verify_selection_hash(s, within.name, within.hash_prefix)
    if sel.kind != SelectionKind.AXIOMS:
        raise SelectionKindError(
            name=within.name,
            expected=SelectionKind.AXIOMS,
            actual=sel.kind,
            operation="remove_axioms",
        )

    removed: list[HashedAxiom] = []
    absent = 0
    items = [
        r[0]
        for r in s.conn.execute(
            "SELECT item FROM selection_items WHERE selection_name = ?", (within.name,)
        )
    ]
    for h in items:
        row = s.conn.execute("SELECT hash, json(data) FROM axioms WHERE hash = ?", (h,)).fetchone()
        if row is None:
            absent += 1
            continue
        full_hash, json_data = row
        axiom = load_axiom(
            json_data, f"axiom {full_hash[:HASH_DISPLAY_LEN]} in remove_by_selection"
        )
        _log_event(s, "del", full_hash, json_data)
        s.conn.execute("DELETE FROM axioms WHERE hash = ?", (full_hash,))
        removed.append(HashedAxiom(axiom=axiom, hash=full_hash))

    return RemoveBySelectionResult(removed=tuple(removed), absent=absent)


def annotate_axiom(
    s: Session,
    hash_prefix: str,
    *,
    add_annotations: list[Annotation] | None = None,
    remove_annotations: list[Annotation] | None = None,
) -> HashedAxiom:
    # A: better name? annotate is kind of one-way toward adding
    """Modify axiom-level metadata annotations. Accepts full hash or unambiguous prefix."""
    add_annotations = add_annotations or []
    remove_annotations = remove_annotations or []

    # A: look at this again, maybe add comments, or at least make it clearer what is going on here

    axiom_id, full_hash, json_data = _resolve_unique_axiom(s, hash_prefix)
    axiom = load_axiom(json_data, f"axiom {full_hash[:HASH_DISPLAY_LEN]} in annotate")

    current = list(axiom.annotations)
    for ann in remove_annotations:
        if ann in current:
            current.remove(ann)
    for ann in add_annotations:
        if ann not in current:
            current.append(ann)

    updated = axiom.model_copy(update={"annotations": tuple(current)})
    new_json = updated.model_dump_json()

    s.conn.execute("UPDATE axioms SET data = jsonb(?) WHERE id = ?", (new_json, axiom_id))

    original = set(axiom.annotations)
    final = set(current)
    actually_added = [a.model_dump() for a in final - original]
    actually_removed = [a.model_dump() for a in original - final]
    if actually_added or actually_removed:
        diff = json.dumps({"added": actually_added, "removed": actually_removed})
        _log_event(s, "annotate", full_hash, annotation_diff=diff)

    repopulate_axiom_text(s, axiom_id, updated.annotations)

    return HashedAxiom(axiom=updated, hash=full_hash)


def replace_axiom(s: Session, old_hash_prefix: str, new_axiom: BaseAxiom) -> ReplaceResult:
    """Atomic delete+add with event tracking.

    Old axiom-level annotations are carried forward onto the new axiom -> annotations
    are excluded from the canonical hash, so the new hash is unaffected. Any
    annotations on the input `new_axiom` are discarded; use `annotate` to modify
    annotations afterwards.

    No-op if new content hashes to the same value as old.
    If new hash matches a different existing axiom: old is deleted, add is skipped
    (the existing axiom keeps its own annotations), event records the mapping.
    """
    if not _HEX_RE.match(
        old_hash_prefix
    ):  # A: we could even have a validate_hash_prefix func that just does the _HEX_RE match or does is_hex or sth and then raises the error, could use that everywhere
        raise InvalidHashError(old_hash_prefix)

    new_h = HashedAxiom.of(new_axiom).hash

    old_id, old_full_hash, old_json = _resolve_unique_axiom(s, old_hash_prefix)
    old_axiom = load_axiom(old_json, f"axiom {old_full_hash[:HASH_DISPLAY_LEN]} in replace")
    old_hashed = HashedAxiom(axiom=old_axiom, hash=old_full_hash)

    if new_h == old_full_hash:
        return ReplaceResult(old=old_hashed, new=old_hashed, was_noop=True)

    # Delete old, then attempt to insert new. If new_h collides with a
    # different existing axiom, INSERT OR IGNORE skips and that axiom keeps
    # its own annotations -> the carry-forward is irrelevant in that case.
    s.conn.execute("DELETE FROM axioms WHERE id = ?", (old_id,))
    new_axiom_id = insert_axiom(s, new_axiom, ignore_existing=True)
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
    new_json = new_axiom.model_dump_json()

    _log_event(
        s,
        "replace",
        new_h,
        new_json,
        replaces_hash=old_full_hash,
    )

    return ReplaceResult(
        old=old_hashed,
        new=HashedAxiom(axiom=new_axiom, hash=new_h),
        was_noop=False,
        was_merged_into_existing=merged,
    )


def _substitute_iri(axiom: BaseAxiom, old_iri: str, new_iri: str) -> BaseAxiom:
    """Walk axiom, replacing each IRI == old_iri with new_iri.

    Only IRI-typed fields are substituted; plain str fields (e.g. LangLiteral.value,
    TypedLiteral.value) are left unchanged even if they coincidentally equal old_iri.
    """
    # cast is correct by construction: _sub returns the same shape it received,
    # and pyright can't model that without overloads for every input type.
    return cast("BaseAxiom", _sub(axiom, old_iri, new_iri))


def _sub(value: object, old_iri: str, new_iri: str):
    # A: needs at least a docstring
    if isinstance(value, IRI):
        return IRI(new_iri) if value == old_iri else value
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
    old_iri: str,
    new_iri: str,
    *,
    within: LockedSelection | None = None,
) -> RenameResult:
    """Replace old_iri with new_iri across all (or scoped) axioms. One batch_id.

    `within`: optional locked AXIOMS selection (`name@hash_prefix`) to restrict the
    rename. The hash prefix is verified against the current selection hash ->
    raises StaleSelectionError on mismatch. Raises SelectionKindError if the
    selection is an entity selection; convert with `axioms_for` first.
    """  # A global: docstrings should adhere to whatever standard, like Raises should be indented and all
    batch = uuid.uuid4().hex[:12]
    results: list[ReplaceResult] = []
    # A global: what is this batch thing here? can we do anything here, like at least do manual batch id generation? or make it also hex like everything else?

    # Candidate reads are inside the transaction to avoid TOCTOU.
    # A global: comment above reads like it was written after I fixed something
    if within is not None:
        sel = verify_selection_hash(s, within.name, within.hash_prefix)
        # A: this kind of call and all seems bad, could we not unify or extract to a func to make it easier to understand?
        if sel.kind != SelectionKind.AXIOMS:
            raise SelectionKindError(
                name=within.name,
                expected=SelectionKind.AXIOMS,
                actual=sel.kind,
                operation="rename_iri",
            )
        # ORDER BY a.hash: candidate iteration order determines event-log
        # insertion order; revert(n=1) replays the last batch in reverse.
        rows = s.conn.execute(
            "SELECT DISTINCT a.hash, json(a.data) FROM axioms a "
            "JOIN axiom_entities ae ON ae.axiom_id = a.id "
            "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
            "WHERE ae.entity_iri = ? ORDER BY a.hash",
            (within.name, old_iri),
        ).fetchall()
    else:
        rows = s.conn.execute(
            "SELECT DISTINCT a.hash, json(a.data) FROM axioms a "
            "JOIN axiom_entities ae ON ae.axiom_id = a.id "
            "WHERE ae.entity_iri = ? ORDER BY a.hash",
            (old_iri,),
        ).fetchall()

    for old_full_hash, old_json_data in rows:
        old_axiom = load_axiom(old_json_data, f"rename {old_iri} -> {new_iri}")
        new_axiom = _substitute_iri(old_axiom, old_iri, new_iri)
        new_h = HashedAxiom.of(new_axiom).hash
        new_json = new_axiom.model_dump_json()
        old_hashed = HashedAxiom(axiom=old_axiom, hash=old_full_hash)
        new_hashed = HashedAxiom(axiom=new_axiom, hash=new_h)

        if new_h == old_full_hash:
            results.append(ReplaceResult(old=old_hashed, new=old_hashed, was_noop=True))
            continue

        s.conn.execute("DELETE FROM axioms WHERE hash = ?", (old_full_hash,))
        merged = insert_axiom(s, new_axiom, ignore_existing=True) is None

        _log_event(
            s,
            "replace",
            new_h,
            new_json,
            replaces_hash=old_full_hash,
            batch_id=batch,
        )
        results.append(
            ReplaceResult(
                old=old_hashed,
                new=new_hashed,
                was_noop=False,
                was_merged_into_existing=merged,
            )
        )

    return RenameResult(old_iri=old_iri, new_iri=new_iri, replaced=tuple(results), batch_id=batch)


def axiom_summary(s: Session, *, within: str | None = None) -> AxiomSummary:
    # A: I feel like by_type = Counter(dict(...)) could be factored out and just have a res or cursor = ... and then return the summary in the end.
    # A global: also, within should point to a SelectionName, no? I guess they are in MCP tools - is there any use case to moving them into? or maybe if we inherit from str, we could also add the validation directly into that inherited type, no? then it would work everywhere? or what could we do? please talk to me about this
    if within is None:
        by_type = Counter(dict(s.conn.execute("SELECT type, COUNT(*) FROM axioms GROUP BY type")))
    else:
        sel = get_selection(s, within)
        if sel.kind == SelectionKind.AXIOMS:
            by_type = Counter(
                dict(
                    s.conn.execute(
                        "SELECT a.type, COUNT(*) FROM axioms a "
                        "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
                        "GROUP BY a.type",
                        (within,),
                    )
                )
            )
        else:  # entities: count axioms mentioning those entities
            by_type = Counter(
                dict(
                    s.conn.execute(
                        "SELECT a.type, COUNT(DISTINCT a.id) FROM axioms a "
                        "JOIN axiom_entities ae ON ae.axiom_id = a.id "
                        "JOIN selection_items si ON si.item = ae.entity_iri "
                        "AND si.selection_name = ? GROUP BY a.type",
                        (within,),
                    )
                )
            )
    return AxiomSummary(total=sum(by_type.values()), by_type=by_type)


# A: bad var name - what is this?
_LOCAL_NAME = "local_name"


def _extract_annotation_value(value: IRI | TypedLiteral | LangLiteral):
    # A: bad function name, very unclear what this is
    if isinstance(value, IRI):
        return str(value)
    return value.value


def insert_axiom(s: Session, axiom: BaseAxiom, *, ignore_existing: bool = False) -> int | None:
    """INSERT axiom row and populate indexes. Returns axiom_id, or None if already existed (ignore_existing=True only)."""
    h = HashedAxiom.of(axiom).hash
    json_data = axiom.model_dump_json()
    verb = (
        "INSERT OR IGNORE" if ignore_existing else "INSERT"
    )  # A: when do we not IGNORE EXISTING? same hash = same axiom, so this is always idempotent. no need to change this. or is there a reason?
    cursor = s.conn.execute(
        f"{verb} INTO axioms (hash, type, data) VALUES (?, ?, jsonb(?))",
        (h, axiom.tag(), json_data),
    )
    if ignore_existing and cursor.rowcount == 0:
        return None
    axiom_id = cursor.lastrowid
    if axiom_id is None:
        msg = "INSERT succeeded but lastrowid is None"  # A: can this ever happen?
        raise InternalError(msg)
    populate(s, axiom, axiom_id)
    return axiom_id


def repopulate_axiom_text(s: Session, axiom_id: int, annotations: tuple[Annotation, ...]) -> None:
    # A: is axiom_id best way to refer to axiom here? why is this not done via hash? any good reason? is it because hash takes a lot of space?
    """Rebuild axiom_text index rows for a single axiom after an annotation change."""
    s.conn.execute("DELETE FROM axiom_text WHERE axiom_id = ?", (axiom_id,))
    rows = [
        (axiom_id, _extract_annotation_value(ann.value), str(ann.property)) for ann in annotations
    ]
    if rows:
        s.conn.executemany(
            "INSERT INTO axiom_text (axiom_id, text, property) VALUES (?, ?, ?)",
            rows,
        )


def populate(s: Session, axiom: BaseAxiom, axiom_id: int) -> None:
    # A: again, naming is bad, return type hints, what does this do, is this internal only?
    """Populate index tables (axiom_entities, entity_text, axiom_text) for a new axiom."""
    entity_rows = []
    text_rows = []
    seen_iris: set[str] = set()

    # A: huge function, seems like it has too many responsibilities

    for iri, role, position in iter_axiom_entities(axiom):
        iri_str = str(iri)
        role_val = role.value if isinstance(role, EntityType) else role
        pos_val = position.value if position is not None else None
        entity_rows.append((axiom_id, iri_str, role_val, pos_val))
        if iri_str not in seen_iris:
            seen_iris.add(iri_str)
            text_rows.append((axiom_id, iri_str, iri.local_name, _LOCAL_NAME))

    if isinstance(axiom, AnnotationAssertion):
        text_rows.append(
            (
                axiom_id,
                str(axiom.subject),
                _extract_annotation_value(axiom.value),
                str(axiom.property),
            )
        )

    s.conn.executemany(
        "INSERT INTO axiom_entities (axiom_id, entity_iri, role, position) VALUES (?, ?, ?, ?)",
        entity_rows,
    )
    s.conn.executemany(
        "INSERT INTO entity_text (axiom_id, entity_iri, text, property) VALUES (?, ?, ?, ?)",
        text_rows,
    )

    axiom_text_rows = [
        (axiom_id, _extract_annotation_value(ann.value), str(ann.property))
        for ann in axiom.annotations
    ]
    if axiom_text_rows:
        s.conn.executemany(
            "INSERT INTO axiom_text (axiom_id, text, property) VALUES (?, ?, ?)",
            axiom_text_rows,
        )
