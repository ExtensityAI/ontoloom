"""Event log queries and revert operations."""

import json
from dataclasses import dataclass, field

from ontoloom.ontology.canonical import truncate_hash
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.indexes import insert_axiom, repopulate_axiom_text
from ontoloom.ontology.load import load_axiom
from ontoloom.ontology.models.literals import Annotation


# A: needs documentation, especially which options there are. also, why do we not do it with like inheritance, like have a pydantic class for this with a base and then a bunch of children with different type values, and then we load different records? this way, in db we do have the merged version with nullable fields, but in code we have the clean event records depending on types? could use op!
# A global: also regarding above, op is a str, but pretty sure it should be a StrEnum? check!
@dataclass
class EventRecord:
    sequence_id: int
    op: str
    axiom_hash: str
    replaces_hash: str | None
    annotation_diff: str | None
    batch_id: str | None
    timestamp: str


# A: needs documentation, why is it just called Batch?
@dataclass  # A global: if you use dataclass, always frozen and slots!
class Batch:
    """A group of events that form one logical operation."""

    events: list[EventRecord] = field(default_factory=list)

    @property
    def batch_id(self) -> str | None:
        # A: this is not good - what is this? why can we not get it from anywhere else?
        return self.events[0].batch_id if self.events else None

    @property
    def size(self) -> int:
        return len(self.events)


# A: name bad? not sure
@dataclass
class RevertReport:
    reverted: int
    skipped: int
    details: list[str]


def show_changes(ont: Ontology, *, session_id: str | None = None) -> list[EventRecord]:
    # A: bad func name, show_changes is not what this does! also, again, return type not needeed?
    # A global: why not iter_...? seems like we do not need a fetchall and can just iterate over and yield
    """Return events for a session (default: current session)."""
    sid = session_id or ont.session_id
    rows = ont.conn.execute(
        "SELECT sequence_id, op, axiom_hash, replaces_hash, annotation_diff, batch_id, timestamp "
        "FROM events WHERE session_id = ? ORDER BY sequence_id",
        (sid,),
    ).fetchall()
    return [
        EventRecord(
            sequence_id=r[0],
            op=r[1],
            axiom_hash=r[2],
            replaces_hash=r[3],
            annotation_diff=r[4],
            batch_id=r[5],
            timestamp=r[6],
        )
        for r in rows
    ]


def _group_into_batches(events: list[EventRecord]) -> list[Batch]:
    # A: what is this? if batch_id is part of events, we can just group them in the sql query, no? or do we need unbatched as well ever? why not batched select by default?
    """Group events into batches. Events with same batch_id form one batch.
    Unbatched events are each their own batch."""
    batches: list[Batch] = []
    current_batch: Batch | None = None

    for event in events:
        if event.batch_id is not None:
            if current_batch is not None and current_batch.batch_id == event.batch_id:
                current_batch.events.append(event)
            else:
                if current_batch is not None:
                    batches.append(current_batch)
                current_batch = Batch(events=[event])
        else:
            if current_batch is not None:
                batches.append(current_batch)
                current_batch = None
            batches.append(Batch(events=[event]))

    if current_batch is not None:
        batches.append(current_batch)

    return batches


def revert(ont: Ontology, n: int = 1) -> RevertReport:
    # A: this needs a proper look, but low priority. not sure if the semantics are good. Naming is bad tho, again. already mentioend in other files.
    """Undo the last N batches in the current session.

    Applies inverses in reverse order. Appends inverse events to the log.
    Skips and reports conflicts (e.g., re-adding a hash that already exists).
    """
    all_events = show_changes(ont)
    batches = _group_into_batches(all_events)

    if n > len(batches):
        n = len(batches)

    # Take last N batches, process in reverse
    to_revert = batches[-n:]
    to_revert.reverse()

    reverted = 0
    skipped = 0
    details: list[str] = []

    with ont.conn:
        for batch in to_revert:
            # Reverse events within batch too
            for event in reversed(batch.events):
                success, detail = _revert_event(ont, event)
                if success:
                    reverted += 1
                else:
                    skipped += 1
                details.append(detail)

    return RevertReport(reverted=reverted, skipped=skipped, details=details)


def _revert_event(ont: Ontology, event: EventRecord) -> tuple[bool, str]:
    """Revert a single event. Returns (success, detail_message)."""
    match event.op:
        case "add":
            return _revert_add(ont, event)
        case "del":
            return _revert_del(ont, event)
        case "replace":
            return _revert_replace(ont, event)
        case "annotate":
            return _revert_annotate(ont, event)
        case _:
            return False, f"Unknown op {event.op!r} for event {event.sequence_id}"


def _revert_add(ont: Ontology, event: EventRecord) -> tuple[bool, str]:
    """Inverse of add = delete."""
    h = event.axiom_hash
    row = ont.conn.execute("SELECT id FROM axioms WHERE hash = ?", (h,)).fetchone()
    if row is None:
        return False, f"skip revert-add [{truncate_hash(h)}]: already deleted"

    ont.conn.execute("DELETE FROM axioms WHERE hash = ?", (h,))
    _log_inverse(ont, "del", h)
    return True, f"reverted add [{truncate_hash(h)}]: deleted"


def _revert_del(ont: Ontology, event: EventRecord) -> tuple[bool, str]:
    """Inverse of delete = re-add from stored JSON."""
    h = event.axiom_hash
    json_data = ont.conn.execute(
        "SELECT json(axiom_json) FROM events WHERE sequence_id = ?", (event.sequence_id,)
    ).fetchone()

    if json_data is None or json_data[0] is None:
        return False, f"skip revert-del [{truncate_hash(h)}]: no stored axiom_json"

    axiom_json = json_data[0]

    # Check if already exists (re-added through another path)
    existing = ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h,)).fetchone()
    if existing is not None:
        return False, f"skip revert-del [{truncate_hash(h)}]: already exists"

    axiom = load_axiom(axiom_json, f"revert-del {truncate_hash(h)}")
    insert_axiom(ont, axiom)
    _log_inverse(ont, "add", h, axiom_json)
    return True, f"reverted del [{truncate_hash(h)}]: re-added"


def _revert_replace(ont: Ontology, event: EventRecord) -> tuple[bool, str]:
    """Inverse of replace: delete new, re-add old."""
    new_h = event.axiom_hash
    old_h = event.replaces_hash

    if old_h is None:
        return False, f"skip revert-replace [{truncate_hash(new_h)}]: no replaces_hash"

    # Find the old axiom's JSON from the original del event (or the replace event itself)
    # The old axiom was deleted — its JSON should be in a prior 'del' or 'replace' event
    old_json_row = ont.conn.execute(
        "SELECT json(axiom_json) FROM events "
        "WHERE axiom_hash = ? AND op IN ('del', 'add') AND axiom_json IS NOT NULL "
        "ORDER BY sequence_id DESC LIMIT 1",
        (old_h,),
    ).fetchone()

    if old_json_row is None or old_json_row[0] is None:
        return (
            False,
            f"skip revert-replace [{truncate_hash(new_h)}->{truncate_hash(old_h)}]: no stored json for old axiom",
        )

    old_json = old_json_row[0]

    # Delete the new axiom (if it exists and isn't used elsewhere)
    ont.conn.execute("DELETE FROM axioms WHERE hash = ?", (new_h,))

    # Re-add old axiom
    existing = ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (old_h,)).fetchone()
    if existing is None:
        old_axiom = load_axiom(old_json, f"revert-replace {truncate_hash(old_h)}")
        insert_axiom(ont, old_axiom)

    _log_inverse(ont, "replace", old_h, old_json, replaces_hash=new_h)
    return True, f"reverted replace [{truncate_hash(new_h)}->{truncate_hash(old_h)}]: restored old"


def _revert_annotate(ont: Ontology, event: EventRecord) -> tuple[bool, str]:
    """Inverse of annotate: apply reverse diff."""
    h = event.axiom_hash

    if event.annotation_diff is None:
        return False, f"skip revert-annotate [{truncate_hash(h)}]: no diff stored"

    row = ont.conn.execute("SELECT id, json(data) FROM axioms WHERE hash = ?", (h,)).fetchone()
    if row is None:
        return False, f"skip revert-annotate [{truncate_hash(h)}]: axiom not found"

    axiom_id, json_data = row
    axiom = load_axiom(json_data, f"revert-annotate {truncate_hash(h)}")
    diff = json.loads(event.annotation_diff)

    # Inverse: remove what was added, add what was removed
    current = list(axiom.annotations)
    for ann_data in diff.get("added", []):
        ann = Annotation.model_validate(ann_data)
        if ann in current:
            current.remove(ann)
    for ann_data in diff.get("removed", []):
        ann = Annotation.model_validate(ann_data)
        if ann not in current:
            current.append(ann)

    updated = axiom.model_copy(update={"annotations": tuple(current)})
    new_json = updated.model_dump_json()
    ont.conn.execute("UPDATE axioms SET data = jsonb(?) WHERE id = ?", (new_json, axiom_id))

    repopulate_axiom_text(ont, axiom_id, updated.annotations)

    # Log inverse annotate event
    inverse_diff = json.dumps(
        {
            "added": diff.get("removed", []),
            "removed": diff.get("added", []),
        }
    )
    _log_inverse(ont, "annotate", h, annotation_diff=inverse_diff)
    return True, f"reverted annotate [{truncate_hash(h)}]: annotations restored"


def _log_inverse(
    ont: Ontology,
    op: str,
    axiom_hash: str,
    axiom_json: str | None = None,
    *,
    replaces_hash: str | None = None,
    annotation_diff: str | None = None,
):
    """Log an inverse event (revert produces new forward events)."""
    ont.conn.execute(
        "INSERT INTO events (session_id, op, axiom_hash, axiom_json, replaces_hash, annotation_diff)"
        " VALUES (?, ?, ?, jsonb(?), ?, ?)",
        (ont.session_id, op, axiom_hash, axiom_json, replaces_hash, annotation_diff),
    )
