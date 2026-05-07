import json

import pytest
from ontoloom.axioms.store import (
    add_axioms,
    annotate_axiom,
    remove_axioms_by_hash,
    rename_iri,
    replace_axiom,
)
from ontoloom.connection import Ontology
from ontoloom.hashing import HashedAxiom
from ontoloom.history import EventRecord, _group_into_batches, revert
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral


@pytest.fixture()
def ont(tmp_path):
    path = tmp_path / "test.ontology.db"
    Ontology.create(path)
    with Ontology(path) as o:
        yield o


def test_revert_add(ont):
    ax = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(ont, [ax])
    h = HashedAxiom.of(ax).hash

    report = revert(ont, n=1)
    assert report.reverted == 1
    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h,)).fetchone() is None


def test_revert_del(ont):
    ax = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(ont, [ax])
    h = HashedAxiom.of(ax).hash
    remove_axioms_by_hash(ont, [h[:8]])

    report = revert(ont, n=1)
    assert report.reverted == 1

    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h,)).fetchone() is not None
    entity_count = ont.conn.execute(
        "SELECT COUNT(*) FROM axiom_entities WHERE axiom_id IN (SELECT id FROM axioms WHERE hash = ?)",
        (h,),
    ).fetchone()[0]
    assert entity_count > 0


def test_revert_del_skip_when_already_exists(ont):
    ax = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(ont, [ax])
    h = HashedAxiom.of(ax).hash
    remove_axioms_by_hash(ont, [h[:8]])
    add_axioms(ont, [ax])  # re-add; now exists again

    # revert(1) reverts the second "add" → deletes it
    report = revert(ont, n=1)
    assert report.reverted == 1
    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h,)).fetchone() is None


def test_revert_replace(ont):
    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="original"))
    ax_old = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(ann,),
    )
    add_axioms(ont, [ax_old])
    old_h = HashedAxiom.of(ax_old).hash

    ax_new = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Mammal"),
    )
    replace_axiom(ont, old_h[:8], ax_new)
    new_h = HashedAxiom.of(ax_new).hash

    report = revert(ont, n=1)
    assert report.reverted == 1

    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (new_h,)).fetchone() is None
    row = ont.conn.execute("SELECT json(data) FROM axioms WHERE hash = ?", (old_h,)).fetchone()
    assert row is not None
    stored = json.loads(row[0])
    assert len(stored.get("annotations", [])) == 1


def test_revert_annotate(ont):
    ax = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(ont, [ax])
    h = HashedAxiom.of(ax).hash
    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="hello"))
    annotate_axiom(ont, h[:8], add_annotations=[ann])

    report = revert(ont, n=1)
    assert report.reverted == 1

    row = ont.conn.execute("SELECT json(data) FROM axioms WHERE hash = ?", (h,)).fetchone()
    assert row is not None
    stored = json.loads(row[0])
    assert stored.get("annotations") == []

    text_count = ont.conn.execute(
        "SELECT COUNT(*) FROM axiom_text WHERE axiom_id IN (SELECT id FROM axioms WHERE hash = ?)",
        (h,),
    ).fetchone()[0]
    assert text_count == 0


def test_revert_rename_iri_batch(ont):
    ax1 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    ax2 = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(ont, [ax1, ax2])
    old_h1 = HashedAxiom.of(ax1).hash
    old_h2 = HashedAxiom.of(ax2).hash

    rename_iri(ont, "ex:Animal", "ex:Organism")

    report = revert(ont, n=1)
    assert report.reverted >= 1

    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (old_h1,)).fetchone() is not None
    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (old_h2,)).fetchone() is not None


def test_revert_two_operations(ont):
    ax1 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    ax2 = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(ont, [ax1])
    add_axioms(ont, [ax2])
    h1 = HashedAxiom.of(ax1).hash
    h2 = HashedAxiom.of(ax2).hash

    report = revert(ont, n=2)
    assert report.reverted >= 2

    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h1,)).fetchone() is None
    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h2,)).fetchone() is None


def test_group_into_batches_interleaved():
    def make_event(seq, batch_id):
        return EventRecord(
            sequence_id=seq,
            op="add",
            axiom_hash="abc" + str(seq),
            replaces_hash=None,
            annotation_diff=None,
            batch_id=batch_id,
            timestamp="2026-01-01T00:00:00",
        )

    events = [
        make_event(1, "batch_A"),
        make_event(2, "batch_A"),
        make_event(3, None),
        make_event(4, "batch_A"),
    ]

    batches = _group_into_batches(events)
    assert len(batches) == 3
    assert [b.size for b in batches] == [2, 1, 1]
