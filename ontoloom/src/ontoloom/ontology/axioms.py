import json
import re
import uuid
from collections import Counter
from collections.abc import Sequence
from typing import cast

from ontoloom.ontology import selections
from ontoloom.ontology.canonical import axiom_hash, min_distinguishing_prefixes, truncate_hash
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.errors import (
    AmbiguousHashError,
    AxiomNotFoundError,
    InvalidHashError,
    SelectionKindError,
)
from ontoloom.ontology.indexes import insert_axiom, repopulate_axiom_text
from ontoloom.ontology.load import load_axiom
from ontoloom.ontology.models._pydantic import FrozenModel
from ontoloom.ontology.models.base import BaseAxiom
from ontoloom.ontology.models.literals import IRI, Annotation
from ontoloom.ontology.types import (
    AddResult,
    AxiomSummary,
    HashedAxiom,
    LockedSelection,
    RemoveBySelectionResult,
    RemoveResult,
    RenameResult,
    ReplaceResult,
    SelectionKind,
)

_HEX_RE = re.compile(r"^[0-9a-f]+$")


def is_valid_hex(s: str):
    # A: is a general utility function, shoudl be moved somewhere better. no need for this complex explanation
    # A global: docs only explain what a func does. also, should be concise. e.g. this does not even need a comment, it is entirely clear what it does. the explanation for what it is used should rather be moved to the actual use location, it has nothing to do with what this function does. make this also a general python principle (like in your python rules or wherever, just like that other one on spacing)
    """True if `s` is a non-empty lowercase hex string. Use to validate hash prefixes
    before they reach SQL — guarantees no LIKE metacharacters can appear."""
    return _HEX_RE.match(s) is not None


def _resolve_unique_axiom(ont: Ontology, prefix: str) -> tuple[int, str, str]:
    """Look up an axiom by hash prefix; raise on missing or ambiguous match. Returns (id, full_hash, json_data)."""
    if not is_valid_hex(prefix):
        raise InvalidHashError(prefix)
    rows = ont.conn.execute(
        "SELECT id, hash, json(data) FROM axioms WHERE hash LIKE ? || '%'",
        (prefix,),
    ).fetchall()
    if not rows:
        raise AxiomNotFoundError(prefix)
    if len(rows) > 1:
        full_hashes = [r[1] for r in rows]
        raise AmbiguousHashError(prefix, len(rows), min_distinguishing_prefixes(full_hashes))
    return rows[0]  # A: returns raw row, very bad, why?


def _log_event(
    # A: why is this not in history? also, I feel like we need multiple funcs to log events, just like we would have multiple event types? these optional args are hard to get right, so make multiple funcs, and why do we take both hash and json? just take the obj, we even have HashedAxiom
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


def add(ont: Ontology, axioms: Sequence[BaseAxiom]) -> AddResult:
    added: list[HashedAxiom] = []
    skipped: list[HashedAxiom] = []

    with ont.conn:
        for axiom in axioms:
            h = axiom_hash(axiom)  # inline into ha creation
            json_data = (
                axiom.model_dump_json()
            )  # A: should be computed where actually needed, this is noise here
            ha = HashedAxiom(axiom=axiom, hash=h)
            if insert_axiom(ont, axiom, ignore_existing=True) is None:
                skipped.append(ha)
                continue
            added.append(ha)
            _log_event(ont, "add", h, json_data)

    return AddResult(added=added, skipped=skipped)


def remove_by_hash(ont: Ontology, hash_prefixes: list[str]) -> RemoveResult:
    # A: name is bad, remove_by_hashes, but then again, I am not sure whether removal by hash prefixes should be done here! is this not a MCP concern? this would also apply to search, so it is not as easy, because if we only allow remove of Axiom instances here, then search would also not allow prefixes? or could it still? what do you think?
    for prefix in hash_prefixes:
        if not is_valid_hex(prefix):
            raise InvalidHashError(prefix)

    with ont.conn:
        to_remove: list[HashedAxiom] = []
        for prefix in hash_prefixes:
            _, full_hash, json_data = _resolve_unique_axiom(ont, prefix)
            axiom = load_axiom(json_data, f"axiom {truncate_hash(full_hash)} in remove_by_hash")
            to_remove.append(HashedAxiom(axiom=axiom, hash=full_hash))

        for ha in to_remove:
            # A: again, unclean because of events, already discussed in detail
            _log_event(ont, "del", ha.hash, ha.axiom.model_dump_json())
            ont.conn.execute("DELETE FROM axioms WHERE hash = ?", (ha.hash,))

    return RemoveResult(removed=to_remove)


def remove_by_selection(ont: Ontology, within: LockedSelection) -> RemoveBySelectionResult:
    # A: I feel like this function should resolve axioms, then use remove_axioms as mentioned above (not with prefix. at least if we keep the remove by prefix, then make a authoritative remove_axioms func s.t. remove by prefix first resolves then calls that, same as this one. saves us a lot of code and ugliness.) might even unify results? or if not, compose or inherit RemoveResult in RemoveBySelectionResult or sth
    """Remove axioms referenced by an axiom selection. Best-effort: skips missing."""
    sel = selections.verify_hash(ont, within.name, within.hash_prefix)
    if sel.kind != SelectionKind.AXIOMS:
        raise SelectionKindError(
            name=within.name,
            expected=SelectionKind.AXIOMS,
            actual=sel.kind,
            operation="remove_axioms",
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
            axiom = load_axiom(
                json_data, f"axiom {truncate_hash(full_hash)} in remove_by_selection"
            )
            _log_event(ont, "del", full_hash, json_data)
            ont.conn.execute("DELETE FROM axioms WHERE hash = ?", (full_hash,))
            removed.append(HashedAxiom(axiom=axiom, hash=full_hash))

    return RemoveBySelectionResult(removed=removed, absent=absent)


def annotate(
    ont: Ontology,
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

    with ont.conn:
        axiom_id, full_hash, json_data = _resolve_unique_axiom(ont, hash_prefix)
        axiom = load_axiom(json_data, f"axiom {truncate_hash(full_hash)} in annotate")

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

        repopulate_axiom_text(ont, axiom_id, updated.annotations)

    return HashedAxiom(axiom=updated, hash=full_hash)


def replace(ont: Ontology, old_hash_prefix: str, new_axiom: BaseAxiom) -> ReplaceResult:
    """Atomic delete+add with event tracking.

    Old axiom-level annotations are carried forward onto the new axiom — annotations
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

    new_h = axiom_hash(new_axiom)

    with ont.conn:
        old_id, old_full_hash, old_json = _resolve_unique_axiom(ont, old_hash_prefix)
        old_axiom = load_axiom(old_json, f"axiom {truncate_hash(old_full_hash)} in replace")
        old_hashed = HashedAxiom(axiom=old_axiom, hash=old_full_hash)

        if new_h == old_full_hash:
            return ReplaceResult(old=old_hashed, new=old_hashed, was_noop=True)

        # Delete old, then attempt to insert new. If new_h collides with a
        # different existing axiom, INSERT OR IGNORE skips and that axiom keeps
        # its own annotations — the carry-forward is irrelevant in that case.
        ont.conn.execute("DELETE FROM axioms WHERE id = ?", (old_id,))
        new_axiom_id = insert_axiom(ont, new_axiom, ignore_existing=True)
        merged = new_axiom_id is None

        if not merged:
            # Carry old axiom-level annotations onto the new axiom; annotations
            # don't enter the canonical hash so new_h is unchanged.
            new_axiom = new_axiom.model_copy(update={"annotations": old_axiom.annotations})
            ont.conn.execute(
                "UPDATE axioms SET data = jsonb(?) WHERE id = ?",
                (new_axiom.model_dump_json(), new_axiom_id),
            )
            repopulate_axiom_text(ont, new_axiom_id, new_axiom.annotations)
        new_json = new_axiom.model_dump_json()

        _log_event(
            ont,
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
    """  # A global: docstrings should adhere to whatever standard, like Raises should be indented and all
    batch = uuid.uuid4().hex[:12]
    results: list[ReplaceResult] = []
    # A global: what is this batch thing here? can we do anything here, like at least do manual batch id generation? or make it also hex like everything else?

    with ont.conn:
        # Candidate reads are inside the transaction to avoid TOCTOU.
        # A global: comment above reads like it was written after I fixed something
        if within is not None:
            sel = selections.verify_hash(ont, within.name, within.hash_prefix)
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
            rows = ont.conn.execute(
                "SELECT DISTINCT a.hash, json(a.data) FROM axioms a "
                "JOIN axiom_entities ae ON ae.axiom_id = a.id "
                "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
                "WHERE ae.entity_iri = ? ORDER BY a.hash",
                (within.name, old_iri),
            ).fetchall()
        else:
            rows = ont.conn.execute(
                "SELECT DISTINCT a.hash, json(a.data) FROM axioms a "
                "JOIN axiom_entities ae ON ae.axiom_id = a.id "
                "WHERE ae.entity_iri = ? ORDER BY a.hash",
                (old_iri,),
            ).fetchall()

        for old_full_hash, old_json_data in rows:
            old_axiom = load_axiom(old_json_data, f"rename {old_iri} -> {new_iri}")
            new_axiom = _substitute_iri(old_axiom, old_iri, new_iri)
            new_h = axiom_hash(new_axiom)
            new_json = new_axiom.model_dump_json()
            old_hashed = HashedAxiom(axiom=old_axiom, hash=old_full_hash)
            new_hashed = HashedAxiom(axiom=new_axiom, hash=new_h)

            if new_h == old_full_hash:
                results.append(ReplaceResult(old=old_hashed, new=old_hashed, was_noop=True))
                continue

            ont.conn.execute("DELETE FROM axioms WHERE hash = ?", (old_full_hash,))
            insert_axiom(ont, new_axiom, ignore_existing=True)

            _log_event(
                ont,
                "replace",
                new_h,
                new_json,
                replaces_hash=old_full_hash,
                batch_id=batch,
            )
            results.append(ReplaceResult(old=old_hashed, new=new_hashed, was_noop=False))

    return RenameResult(old_iri=old_iri, new_iri=new_iri, replaced=results, batch_id=batch)


def summary(ont: Ontology, *, within: str | None = None) -> AxiomSummary:
    # A: I feel like by_type = Counter(dict(...)) could be factored out and just have a res or cursor = ... and then return the summary in the end.
    # A global: also, within should point to a SelectionName, no? I guess they are in MCP tools - is there any use case to moving them into? or maybe if we inherit from str, we could also add the validation directly into that inherited type, no? then it would work everywhere? or what could we do? please talk to me about this
    if within is None:
        by_type = Counter(dict(ont.conn.execute("SELECT type, COUNT(*) FROM axioms GROUP BY type")))
    else:
        sel = selections.get(ont, within)
        if sel.kind == SelectionKind.AXIOMS:
            by_type = Counter(
                dict(
                    ont.conn.execute(
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
                    ont.conn.execute(
                        "SELECT a.type, COUNT(DISTINCT a.id) FROM axioms a "
                        "JOIN axiom_entities ae ON ae.axiom_id = a.id "
                        "JOIN selection_items si ON si.item = ae.entity_iri "
                        "AND si.selection_name = ? GROUP BY a.type",
                        (within,),
                    )
                )
            )
    return AxiomSummary(total=sum(by_type.values()), by_type=by_type)
