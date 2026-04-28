import json

import pytest
from ontoloom.ontology import axioms, entities, export, prefixes, selections
from ontoloom.ontology.canonical import axiom_hash
from ontoloom.ontology.connection import Ontology, StoreNotOpenError
from ontoloom.ontology.errors import (
    AxiomNotFoundError,
    InvalidHashError,
    OntologyExistsError,
    OntologyNotFoundError,
    PrefixNotFoundError,
    SelectionKindError,
)
from ontoloom.ontology.models.axioms import (
    AnnotationAssertion,
    Declaration,
    EquivalentClasses,
    SubClassOf,
)
from ontoloom.ontology.models.base import EntityType
from ontoloom.ontology.models.expressions import NamedClass, ObjectSomeValuesFrom
from ontoloom.ontology.models.literals import IRI, Annotation, LangLiteral
from ontoloom.ontology.types import LockedSelection, Position, SelectionKind


@pytest.fixture()
def ont(tmp_path):
    path = tmp_path / "test.ontology.db"
    Ontology.create(path)
    with Ontology(path) as o:
        yield o


@pytest.fixture()
def populated(ont):
    axioms.add(
        ont,
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
        ],
    )
    return ont


# -- Logical hashing --


def test_annotations_do_not_affect_dedup(ont):
    ax1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    ax2 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
        annotations=(Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note")),),
    )
    result1 = axioms.add(ont, [ax1])
    assert len(result1.added) == 1

    result2 = axioms.add(ont, [ax2])
    assert len(result2.skipped) == 1
    assert len(result2.added) == 0
    assert result1.added[0].hash == result2.skipped[0].hash


def test_set_semantic_dedup(ont):
    ax1 = EquivalentClasses(expressions=(NamedClass(iri=IRI("ex:A")), NamedClass(iri=IRI("ex:B"))))
    ax2 = EquivalentClasses(expressions=(NamedClass(iri=IRI("ex:B")), NamedClass(iri=IRI("ex:A"))))
    result = axioms.add(ont, [ax1, ax2])
    assert len(result.added) == 1
    assert len(result.skipped) == 1


# -- Annotate axiom --


def test_annotate_axiom_updates_in_place(ont):
    ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    result = axioms.add(ont, [ax])
    h = result.added[0].hash

    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="important"))
    updated = axioms.annotate(ont, h, add_annotations=[ann])

    assert updated.hash == h
    assert len(updated.axiom.annotations) == 1
    assert updated.axiom.annotations[0].value.value == "important"


def test_annotate_axiom_remove(ont):
    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note"))
    ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
        annotations=(ann,),
    )
    result = axioms.add(ont, [ax])
    h = result.added[0].hash

    updated = axioms.annotate(ont, h, remove_annotations=[ann])
    assert len(updated.axiom.annotations) == 0


def test_annotate_nonexistent_raises(ont):
    with pytest.raises(AxiomNotFoundError):
        axioms.annotate(ont, "deadbeef", add_annotations=[])


# -- Annotation preservation across content-hash changes --


def test_replace_preserves_old_annotations(ont):
    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="kept"))
    old = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
        annotations=(ann,),
    )
    axioms.add(ont, [old])
    old_h = axiom_hash(old)

    new = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Mammal")),
    )
    result = axioms.replace(ont, old_h, new)
    assert not result.was_noop

    row = ont.conn.execute(
        "SELECT json(data) FROM axioms WHERE hash = ?", (result.new_hash,)
    ).fetchone()
    stored = json.loads(row[0])
    assert stored["annotations"] == [ann.model_dump(mode="json")]


def test_replace_discards_new_axiom_annotations(ont):
    old = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    axioms.add(ont, [old])
    old_h = axiom_hash(old)

    new = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Mammal")),
        annotations=(Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="ignored")),),
    )
    result = axioms.replace(ont, old_h, new)

    row = ont.conn.execute(
        "SELECT json(data) FROM axioms WHERE hash = ?", (result.new_hash,)
    ).fetchone()
    stored = json.loads(row[0])
    # Old axiom had no annotations; new_axiom's annotations are discarded.
    assert stored["annotations"] == []


def test_rename_iri_rejects_entity_selection(ont):
    axioms.add(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            SubClassOf(
                sub_class=NamedClass(iri=IRI("ex:Dog")),
                super_class=NamedClass(iri=IRI("ex:Animal")),
            ),
        ],
    )
    h, _, _ = selections.write(ont, "dogs", SelectionKind.ENTITIES, ["ex:Dog"], "test")
    locked = LockedSelection(f"dogs@{h}")

    with pytest.raises(SelectionKindError):
        axioms.rename_iri(ont, "ex:Animal", "ex:Mammal", within=locked)


def test_rename_iri_preserves_annotations(ont):
    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="kept"))
    ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
        annotations=(ann,),
    )
    axioms.add(ont, [ax])

    result = axioms.rename_iri(ont, "ex:Animal", "ex:Mammal")
    assert len(result.replaced) == 1
    assert not result.replaced[0].was_noop

    row = ont.conn.execute(
        "SELECT json(data) FROM axioms WHERE hash = ?", (result.replaced[0].new_hash,)
    ).fetchone()
    stored = json.loads(row[0])
    assert stored["annotations"] == [ann.model_dump(mode="json")]


# -- Event log --


def test_events_logged_on_add(ont):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    axioms.add(ont, [ax])

    cur = ont.conn.cursor()
    cur.execute("SELECT op, axiom_hash FROM events")
    events = cur.fetchall()
    assert len(events) == 1
    assert events[0][0] == "add"
    assert events[0][1] == axiom_hash(ax)


def test_events_logged_on_remove(ont):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    result = axioms.add(ont, [ax])
    h = result.added[0].hash

    axioms.remove_by_hash(ont, [h[:8]])

    cur = ont.conn.cursor()
    cur.execute("SELECT op, axiom_hash FROM events ORDER BY sequence_id")
    events = cur.fetchall()
    assert len(events) == 2
    assert events[0] == ("add", h)
    assert events[1] == ("del", h)


def test_events_logged_on_annotate(ont):
    ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    result = axioms.add(ont, [ax])
    h = result.added[0].hash

    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note"))
    axioms.annotate(ont, h, add_annotations=[ann])

    cur = ont.conn.cursor()
    cur.execute("SELECT op, axiom_hash FROM events ORDER BY sequence_id")
    events = cur.fetchall()
    assert len(events) == 2
    assert events[0] == ("add", h)
    assert events[1] == ("annotate", h)


def test_session_id_set(ont):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    axioms.add(ont, [ax])

    cur = ont.conn.cursor()
    cur.execute("SELECT session_id FROM events")
    session_id = cur.fetchone()[0]
    assert session_id is not None
    assert len(session_id) > 0


# -- Prefix management --


def test_set_and_list_prefixes(ont):
    prefixes.set(ont, "ex", "http://example.org/")
    prefixes.set(ont, "rdfs", "http://www.w3.org/2000/01/rdf-schema#")
    assert prefixes.list_all(ont) == {
        "ex": "http://example.org/",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    }


def test_set_prefix_overwrites(ont):
    prefixes.set(ont, "ex", "http://example.org/v1/")
    prefixes.set(ont, "ex", "http://example.org/v2/")
    assert prefixes.list_all(ont)["ex"] == "http://example.org/v2/"


def test_remove_prefix(ont):
    prefixes.set(ont, "ex", "http://example.org/")
    prefixes.set(ont, "rdfs", "http://www.w3.org/2000/01/rdf-schema#")
    prefixes.remove(ont, "ex")
    result = prefixes.list_all(ont)
    assert "ex" not in result
    assert "rdfs" in result


def test_remove_nonexistent_prefix_raises(ont):
    with pytest.raises(PrefixNotFoundError):
        prefixes.remove(ont, "nonexistent")


# -- search_entities --


def test_search_entities_text_query(populated):
    page = entities.search(populated, query="Dog", limit=10, offset=0)
    iris = [m.iri for m in page.matches]
    assert IRI("ex:Dog") in iris


def test_search_entities_role_filter(populated):
    page = entities.search(populated, role="ObjectProperty", limit=10, offset=0)
    iris = [m.iri for m in page.matches]
    assert IRI("ex:hasOwner") in iris
    assert IRI("ex:Dog") not in iris


def test_search_entities_namespace_filter(populated):
    page = entities.search(populated, namespace="other", limit=10, offset=0)
    iris = [m.iri for m in page.matches]
    assert IRI("other:Fish") in iris
    assert IRI("ex:Dog") not in iris


def test_search_entities_combined_filters(populated):
    page = entities.search(populated, query="Dog", role="Class", limit=10, offset=0)
    iris = [m.iri for m in page.matches]
    assert IRI("ex:Dog") in iris


def test_search_entities_pagination(populated):
    page1 = entities.search(populated, limit=2, offset=0)
    page2 = entities.search(populated, limit=2, offset=2)
    iris1 = {m.iri for m in page1.matches}
    iris2 = {m.iri for m in page2.matches}
    assert len(iris1 & iris2) == 0
    assert page1.total == page2.total


def test_search_entities_no_filters(populated):
    page = entities.search(populated, limit=100, offset=0)
    assert page.total >= 5


# -- Export JSONL --


def test_export_jsonl(populated, tmp_path):
    export_path = tmp_path / "export.jsonl"
    count = export.to_jsonl(populated, export_path)
    assert count == 8

    lines = export_path.read_text().strip().split("\n")
    assert len(lines) == 8

    for line in lines:
        obj = json.loads(line)
        assert "type" in obj


# -- entity_text cleanup regression --


def test_entity_text_survives_partial_removal(ont):
    """Removing one axiom that mentions an entity must not break search for that entity
    if other axioms still reference it."""
    ax1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    ax2 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    result = axioms.add(ont, [ax1, ax2])

    # Remove the SubClassOf but keep the Declaration
    subclassof_hash = next(ha.hash for ha in result.added if ha.axiom.type == "SubClassOf")
    axioms.remove_by_hash(ont, [subclassof_hash[:8]])

    # ex:Dog should still be searchable (Declaration still references it)
    page = entities.search(ont, query="Dog", limit=10)
    iris = [m.iri for m in page.matches]
    assert IRI("ex:Dog") in iris


def test_pagination_pages_are_nonempty(populated):
    """Pagination pages should actually contain results (not vacuously pass)."""
    page1 = entities.search(populated, limit=2, offset=0)
    page2 = entities.search(populated, limit=2, offset=2)
    assert len(page1.matches) == 2
    assert len(page2.matches) > 0


# -- get_entity --


def test_get_entity_found(populated):
    info = entities.get(populated, IRI("ex:Dog"))
    assert info is not None
    assert EntityType.CLASS in info.roles
    assert any(a.value == "Dog" for a in info.annotations)
    assert "SubClassOf" in info.axiom_counts


def test_get_entity_not_found(ont):
    assert entities.get(ont, IRI("ex:NonExistent")) is None


# -- remove error cases --


def test_remove_not_found_raises(ont):
    with pytest.raises(AxiomNotFoundError):
        axioms.remove_by_hash(ont, ["deadbeef"])


def test_remove_ambiguous_prefix_raises(ont):
    """An empty prefix is rejected as invalid hex."""
    axioms.add(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
        ],
    )
    # Empty prefix matches everything via GLOB '*'
    with pytest.raises(InvalidHashError):
        axioms.remove_by_hash(ont, [""])


# -- annotate searchability --


# -- export roundtrip --


def test_export_jsonl_roundtrip(populated, tmp_path):
    """Exported JSONL lines should parse back to valid axioms."""
    from ontoloom.ontology.models.axioms import Axiom
    from pydantic import TypeAdapter

    adapter = TypeAdapter(Axiom)
    export_path = tmp_path / "roundtrip.jsonl"
    export.to_jsonl(populated, export_path)

    for line in export_path.read_text().strip().split("\n"):
        axiom = adapter.validate_json(line)
        assert hasattr(axiom, "type")


# -- INSTR safety --


def test_search_with_like_wildcards(ont):
    """Search queries containing % and _ should match literally, not as wildcards."""
    axioms.add(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Rate100Percent")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Rate100Points")),
        ],
    )
    # "100%" should NOT match "100Points" — the % must be literal
    page = entities.search(ont, query="100%", limit=10)
    for m in page.matches:
        assert "100%" in str(m.iri) or "100%" in m.iri.local_name


def test_namespace_filter_escapes_underscore(ont):
    """Underscore in a prefix must be matched literally, not as SQL LIKE wildcard."""
    axioms.add(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("a_b:X")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("aXb:Y")),
        ],
    )
    iris = entities.collect_iris(ont, namespace="a_b")
    # Without ESCAPE, `a_b:%` would match `aXb:Y` because `_` is a LIKE wildcard.
    assert "a_b:X" in iris
    assert "aXb:Y" not in iris


def test_remove_selections_by_pattern(ont):
    axioms.add(ont, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    selections.write(ont, "audit_one", SelectionKind.ENTITIES, ["ex:Dog"], "test")
    selections.write(ont, "audit_two", SelectionKind.ENTITIES, ["ex:Dog"], "test")
    selections.write(ont, "keep", SelectionKind.ENTITIES, ["ex:Dog"], "test")

    dropped = selections.remove_by_pattern(ont, "audit_*")
    names = [n for n, _ in dropped]
    assert names == ["audit_one", "audit_two"]
    assert {s.name for s in selections.list_all(ont)} == {"keep"}


# -- IRI validation --


def test_iri_valid_cases():
    assert IRI(":Dog") == ":Dog"
    assert IRI("owl:Thing") == "owl:Thing"
    assert IRI("ex:a:b") == "ex:a:b"  # colon in local name is fine
    assert IRI("my_ont:Foo") == "my_ont:Foo"  # underscore in prefix


def test_iri_rejects_empty():
    with pytest.raises(ValueError, match="prefix:local_name"):
        IRI("")


def test_iri_rejects_no_colon():
    with pytest.raises(ValueError, match="prefix:local_name"):
        IRI("nocolon")


def test_iri_rejects_empty_local_name():
    with pytest.raises(ValueError, match="prefix:local_name"):
        IRI("prefix:")


def test_iri_rejects_control_chars():
    with pytest.raises(ValueError):
        IRI("ex:foo\nbar")
    with pytest.raises(ValueError):
        IRI("ex:foo\x00bar")


def test_iri_rejects_invalid_prefix():
    with pytest.raises(ValueError):
        IRI("1bad:foo")  # starts with digit
    with pytest.raises(ValueError):
        IRI("a%b:foo")  # % in prefix


# -- Store lifecycle errors --


def test_create_existing_raises(tmp_path):
    path = tmp_path / "test.db"
    Ontology.create(path)
    with pytest.raises(OntologyExistsError):
        Ontology.create(path)


def test_open_nonexistent_raises(tmp_path):
    path = tmp_path / "does_not_exist.db"
    with pytest.raises(OntologyNotFoundError):
        Ontology(path)


def test_conn_outside_context_raises(tmp_path):
    path = tmp_path / "test.db"
    Ontology.create(path)
    o = Ontology(path)
    with pytest.raises(StoreNotOpenError):
        _ = o.conn


# -- Batch remove atomicity --


def test_batch_remove_multiple(ont):
    ax1 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A"))
    ax2 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B"))
    result = axioms.add(ont, [ax1, ax2])
    h1 = result.added[0].hash
    h2 = result.added[1].hash

    removed = axioms.remove_by_hash(ont, [h1[:8], h2[:8]])
    assert len(removed.removed) == 2


def test_batch_remove_rollback_on_failure(ont):
    """If one prefix in a batch fails, none should be removed."""
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A"))
    result = axioms.add(ont, [ax])
    h = result.added[0].hash

    with pytest.raises(AxiomNotFoundError):
        axioms.remove_by_hash(ont, [h[:8], "deadbeef"])

    # The first axiom should still exist (rollback)
    count = ont.conn.execute("SELECT COUNT(*) FROM axioms").fetchone()[0]
    assert count == 1


# -- Hash prefix validation --


def test_remove_rejects_non_hex_prefix(ont):
    with pytest.raises(InvalidHashError):
        axioms.remove_by_hash(ont, ["not*hex"])


# -- Selection: entities_in with field (position filter) --


@pytest.fixture()
def axiom_selection(ont):
    """Create an axiom selection containing SubClassOf and ObjectSomeValuesFrom axioms."""
    result = axioms.add(
        ont,
        [
            SubClassOf(
                sub_class=NamedClass(iri=IRI("ex:Dog")),
                super_class=NamedClass(iri=IRI("ex:Animal")),
            ),
            SubClassOf(
                sub_class=NamedClass(iri=IRI("ex:Cat")),
                super_class=ObjectSomeValuesFrom(
                    property=IRI("ex:hasOwner"),
                    filler=NamedClass(iri=IRI("ex:Person")),
                ),
            ),
        ],
    )
    hashes = [ha.hash for ha in result.added]
    selections.write(ont, "ax_sel", SelectionKind.AXIOMS, hashes, "test")
    return ont


def test_entities_in_with_field_sub_class(axiom_selection):
    selections.create(
        axiom_selection, "sub_classes", entities_in="ax_sel", field=Position.SUB_CLASS
    )
    items = [
        r[0]
        for r in axiom_selection.conn.execute(
            "SELECT item FROM selection_items WHERE selection_name = ?", ("sub_classes",)
        )
    ]
    assert set(items) == {"ex:Dog", "ex:Cat"}


def test_entities_in_with_field_super_class(axiom_selection):
    selections.create(
        axiom_selection, "super_classes", entities_in="ax_sel", field=Position.SUPER_CLASS
    )
    items = [
        r[0]
        for r in axiom_selection.conn.execute(
            "SELECT item FROM selection_items WHERE selection_name = ?", ("super_classes",)
        )
    ]
    # Only the first SubClassOf has a named super_class (ex:Animal).
    # The second has ObjectSomeValuesFrom — no entity in super_class position.
    assert set(items) == {"ex:Animal"}


def test_entities_in_with_field_filler(axiom_selection):
    selections.create(axiom_selection, "fillers", entities_in="ax_sel", field=Position.FILLER)
    items = [
        r[0]
        for r in axiom_selection.conn.execute(
            "SELECT item FROM selection_items WHERE selection_name = ?", ("fillers",)
        )
    ]
    assert set(items) == {"ex:Person"}


def test_entities_in_without_field(axiom_selection):
    selections.create(axiom_selection, "all_ents", entities_in="ax_sel")
    items = [
        r[0]
        for r in axiom_selection.conn.execute(
            "SELECT item FROM selection_items WHERE selection_name = ?", ("all_ents",)
        )
    ]
    # All entities across both axioms, any position
    assert "ex:Dog" in items
    assert "ex:Cat" in items
    assert "ex:Animal" in items
    assert "ex:Person" in items
    assert "ex:hasOwner" in items


# -- Prefix usage counts --


def test_prefix_usage_counts(ont):
    prefixes.set(ont, "ex", "http://example.org/")
    prefixes.set(ont, "other", "http://other.org/")
    prefixes.set(ont, "unused", "http://unused.org/")

    axioms.add(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("other:Fish")),
        ],
    )

    counts = prefixes.usage_counts(ont)
    assert counts["ex"] == 2
    assert counts["other"] == 1
    assert counts["unused"] == 0


# -- CURIE validation --


def test_validate_curie_valid(ont):
    prefixes.set(ont, "ex", "http://example.org/")
    prefixes.validate_curie(ont, "ex:Dog")  # should not raise


def test_validate_curie_invalid(ont):
    prefixes.set(ont, "GO", "http://purl.obolibrary.org/obo/GO_")
    prefixes.set(ont, "rdfs", "http://www.w3.org/2000/01/rdf-schema#")

    with pytest.raises(ValueError, match="Unknown prefix 'GO_'"):
        prefixes.validate_curie(ont, "GO_:0005634")


def test_validate_curie_full_uri_skipped(ont):
    # Full URIs are not CURIEs — validation should be skipped
    prefixes.validate_curie(ont, "http://example.org/Dog")  # should not raise
