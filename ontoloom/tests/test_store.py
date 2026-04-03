"""Tests for OntologyStore."""

import json

import pytest
from ontoloom.core.ontology.canonical import content_hash
from ontoloom.core.ontology.models.axioms import (
    AnnotationAssertion,
    Declaration,
    EquivalentClasses,
    SubClassOf,
)
from ontoloom.core.ontology.models.base import EntityType
from ontoloom.core.ontology.models.expressions import NamedClass
from ontoloom.core.ontology.models.literals import IRI, Annotation, LangLiteral
from ontoloom.core.ontology.store import OntologyStore


@pytest.fixture()
def store(tmp_path):
    path = tmp_path / "test.ontology.db"
    OntologyStore.create(path)
    with OntologyStore(path) as s:
        yield s


@pytest.fixture()
def populated_store(store):
    store.add_axioms(
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI("ex:hasOwner")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("other:Fish")),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Dog"),
                value=LangLiteral(value="Dog"),
            ),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Cat"),
                value=LangLiteral(value="Cat"),
            ),
            SubClassOf(
                sub_class=NamedClass(iri=IRI("ex:Dog")),
                super_class=NamedClass(iri=IRI("ex:Animal")),
            ),
        ]
    )
    return store


# -- Logical hashing --


def test_annotations_do_not_affect_dedup(store):
    ax1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    ax2 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
        annotations=(Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note")),),
    )
    result1 = store.add_axioms([ax1])
    assert len(result1.added) == 1

    result2 = store.add_axioms([ax2])
    assert len(result2.skipped) == 1
    assert len(result2.added) == 0
    assert result1.added[0].hash == result2.skipped[0].hash


def test_set_semantic_dedup(store):
    ax1 = EquivalentClasses(expressions=(NamedClass(iri=IRI("ex:A")), NamedClass(iri=IRI("ex:B"))))
    ax2 = EquivalentClasses(expressions=(NamedClass(iri=IRI("ex:B")), NamedClass(iri=IRI("ex:A"))))
    result = store.add_axioms([ax1, ax2])
    assert len(result.added) == 1
    assert len(result.skipped) == 1


# -- Annotate axiom --


def test_annotate_axiom_updates_in_place(store):
    ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    result = store.add_axioms([ax])
    axiom_hash = result.added[0].hash

    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="important"))
    updated = store.annotate_axiom(axiom_hash, add_annotations=[ann])

    assert updated.hash == axiom_hash
    assert len(updated.axiom.annotations) == 1
    assert updated.axiom.annotations[0].value.value == "important"

    page = store.search_axioms(iri=IRI("ex:Dog"), axiom_types=["SubClassOf"])
    found = [ha for ha in page.axioms if ha.hash == axiom_hash]
    assert len(found) == 1
    assert len(found[0].axiom.annotations) == 1


def test_annotate_axiom_remove(store):
    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note"))
    ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
        annotations=(ann,),
    )
    result = store.add_axioms([ax])
    axiom_hash = result.added[0].hash

    updated = store.annotate_axiom(axiom_hash, remove_annotations=[ann])
    assert len(updated.axiom.annotations) == 0


def test_annotate_nonexistent_raises(store):
    with pytest.raises(ValueError, match="No axiom"):
        store.annotate_axiom("deadbeef", add_annotations=[])


# -- Event log --


def test_events_logged_on_add(store):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    store.add_axioms([ax])

    cur = store.conn.cursor()
    cur.execute("SELECT op, axiom_hash FROM events")
    events = cur.fetchall()
    assert len(events) == 1
    assert events[0][0] == "add"
    assert events[0][1] == content_hash(ax)


def test_events_logged_on_remove(store):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    result = store.add_axioms([ax])
    h = result.added[0].hash

    store.remove_by_hash_prefix([h[:8]])

    cur = store.conn.cursor()
    cur.execute("SELECT op, axiom_hash FROM events ORDER BY sequence_id")
    events = cur.fetchall()
    assert len(events) == 2
    assert events[0] == ("add", h)
    assert events[1] == ("del", h)


def test_events_logged_on_annotate(store):
    ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    result = store.add_axioms([ax])
    h = result.added[0].hash

    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note"))
    store.annotate_axiom(h, add_annotations=[ann])

    cur = store.conn.cursor()
    cur.execute("SELECT op, axiom_hash FROM events ORDER BY sequence_id")
    events = cur.fetchall()
    assert len(events) == 3
    assert events[0] == ("add", h)
    assert events[1] == ("del", h)
    assert events[2] == ("add", h)


def test_session_id_set(store):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    store.add_axioms([ax])

    cur = store.conn.cursor()
    cur.execute("SELECT session_id FROM events")
    session_id = cur.fetchone()[0]
    assert session_id is not None
    assert len(session_id) > 0


# -- Prefix management --


def test_set_and_list_prefixes(store):
    store.set_prefix("ex", "http://example.org/")
    store.set_prefix("rdfs", "http://www.w3.org/2000/01/rdf-schema#")
    assert store.list_prefixes() == {
        "ex": "http://example.org/",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    }


def test_set_prefix_overwrites(store):
    store.set_prefix("ex", "http://example.org/v1/")
    store.set_prefix("ex", "http://example.org/v2/")
    assert store.list_prefixes()["ex"] == "http://example.org/v2/"


def test_remove_prefix(store):
    store.set_prefix("ex", "http://example.org/")
    store.set_prefix("rdfs", "http://www.w3.org/2000/01/rdf-schema#")
    store.remove_prefix("ex")
    prefixes = store.list_prefixes()
    assert "ex" not in prefixes
    assert "rdfs" in prefixes


def test_remove_nonexistent_prefix_raises(store):
    with pytest.raises(ValueError, match="no prefix"):
        store.remove_prefix("nonexistent")


# -- search_entities --


def test_search_entities_text_query(populated_store):
    page = populated_store.search_entities(query="Dog", limit=10, offset=0)
    iris = [m.iri for m in page.matches]
    assert IRI("ex:Dog") in iris


def test_search_entities_role_filter(populated_store):
    page = populated_store.search_entities(role="ObjectProperty", limit=10, offset=0)
    iris = [m.iri for m in page.matches]
    assert IRI("ex:hasOwner") in iris
    assert IRI("ex:Dog") not in iris


def test_search_entities_namespace_filter(populated_store):
    page = populated_store.search_entities(namespace="other", limit=10, offset=0)
    iris = [m.iri for m in page.matches]
    assert IRI("other:Fish") in iris
    assert IRI("ex:Dog") not in iris


def test_search_entities_combined_filters(populated_store):
    page = populated_store.search_entities(query="Dog", role="Class", limit=10, offset=0)
    iris = [m.iri for m in page.matches]
    assert IRI("ex:Dog") in iris


def test_search_entities_pagination(populated_store):
    page1 = populated_store.search_entities(limit=2, offset=0)
    page2 = populated_store.search_entities(limit=2, offset=2)
    iris1 = {m.iri for m in page1.matches}
    iris2 = {m.iri for m in page2.matches}
    assert len(iris1 & iris2) == 0
    assert page1.total == page2.total


def test_search_entities_no_filters(populated_store):
    page = populated_store.search_entities(limit=100, offset=0)
    assert page.total >= 5


# -- search_axioms --


def test_search_axioms_by_iri(populated_store):
    page = populated_store.search_axioms(iri=IRI("ex:Dog"), limit=50, offset=0)
    assert page.total > 0


def test_search_axioms_by_type(populated_store):
    page = populated_store.search_axioms(axiom_types=["Declaration"], limit=50, offset=0)
    assert all(ha.axiom.type == "Declaration" for ha in page.axioms)
    assert page.total == 5


def test_search_axioms_by_iri_and_type(populated_store):
    page = populated_store.search_axioms(
        iri=IRI("ex:Dog"), axiom_types=["SubClassOf"], limit=50, offset=0
    )
    assert all(ha.axiom.type == "SubClassOf" for ha in page.axioms)
    assert page.total >= 1


def test_search_axioms_by_annotation_query(store):
    ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
        annotations=(
            Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="reviewed by expert")),
        ),
    )
    store.add_axioms([ax])
    page = store.search_axioms(annotation_query="expert", limit=50, offset=0)
    assert page.total >= 1


def test_search_axioms_no_filters(populated_store):
    page = populated_store.search_axioms(limit=100, offset=0)
    assert page.total == 8


def test_search_axioms_pagination(populated_store):
    page1 = populated_store.search_axioms(limit=3, offset=0)
    page2 = populated_store.search_axioms(limit=3, offset=3)
    hashes1 = {ha.hash for ha in page1.axioms}
    hashes2 = {ha.hash for ha in page2.axioms}
    assert len(hashes1 & hashes2) == 0
    assert page1.total == page2.total


# -- Export JSONL --


def test_export_jsonl(populated_store, tmp_path):
    export_path = tmp_path / "export.jsonl"
    count = populated_store.export_jsonl(export_path)
    assert count == 8

    lines = export_path.read_text().strip().split("\n")
    assert len(lines) == 8

    for line in lines:
        obj = json.loads(line)
        assert "type" in obj


# -- entity_text cleanup regression --


def test_entity_text_survives_partial_removal(store):
    """Removing one axiom that mentions an entity must not break search for that entity
    if other axioms still reference it."""
    ax1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    ax2 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    result = store.add_axioms([ax1, ax2])

    # Remove the SubClassOf but keep the Declaration
    subclassof_hash = next(ha.hash for ha in result.added if ha.axiom.type == "SubClassOf")
    store.remove_by_hash_prefix([subclassof_hash[:8]])

    # ex:Dog should still be searchable (Declaration still references it)
    page = store.search_entities(query="Dog", limit=10)
    iris = [m.iri for m in page.matches]
    assert IRI("ex:Dog") in iris


def test_pagination_pages_are_nonempty(populated_store):
    """Pagination pages should actually contain results (not vacuously pass)."""
    page1 = populated_store.search_entities(limit=2, offset=0)
    page2 = populated_store.search_entities(limit=2, offset=2)
    assert len(page1.matches) == 2
    assert len(page2.matches) > 0
