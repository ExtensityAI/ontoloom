import json

import pytest
from ontoloom.ontology import axioms, entities, export, prefixes, selections
from ontoloom.ontology.canonical import axiom_hash
from ontoloom.ontology.connection import Ontology, StoreNotOpenError
from ontoloom.ontology.errors import (
    AmbiguousHashError,
    AxiomNotFoundError,
    BadRequestError,
    InvalidHashError,
    OntologyExistsError,
    OntologyNotFoundError,
    OntologySchemaError,
    PrefixNotFoundError,
    SelectionKindError,
    StoreCorruptionError,
)
from ontoloom.ontology.load import load_axiom
from ontoloom.ontology.models.axioms import (
    AnnotationAssertion,
    Axiom,
    Declaration,
    EquivalentClasses,
    HasKey,
    SubClassOf,
)
from ontoloom.ontology.models.expressions import NamedClass, ObjectSomeValuesFrom
from ontoloom.ontology.models.literals import IRI, Annotation, EntityType, LangLiteral, Position
from ontoloom.ontology.types import LockedSelection, SelectionKind
from pydantic import TypeAdapter


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
    annotation_value = updated.axiom.annotations[0].value
    assert isinstance(annotation_value, LangLiteral)
    assert annotation_value.value == "important"


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
    h = selections.upsert(ont, "dogs", SelectionKind.ENTITIES, ["ex:Dog"], "test").content_hash
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


def test_rename_iri_does_not_corrupt_literal_values(ont):
    # AnnotationAssertion whose subject IS the renamed IRI and whose value string
    # coincidentally equals it. Only the IRI-typed subject field must be rewritten.
    ax = AnnotationAssertion(
        property=IRI("rdfs:comment"),
        subject=IRI("ex:Animal"),
        value=LangLiteral(value="ex:Animal"),
    )
    axioms.add(ont, [ax])

    result = axioms.rename_iri(ont, "ex:Animal", "ex:Mammal")
    assert len(result.replaced) == 1

    row = ont.conn.execute(
        "SELECT json(data) FROM axioms WHERE hash = ?", (result.replaced[0].new_hash,)
    ).fetchone()
    stored = json.loads(row[0])
    assert stored["subject"] == "ex:Mammal"  # IRI field renamed
    assert stored["value"]["value"] == "ex:Animal"  # literal value unchanged


def test_rename_iri_noop_when_iri_absent(ont):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    axioms.add(ont, [ax])

    result = axioms.rename_iri(ont, "ex:Cat", "ex:Kitten")
    assert result.replaced == []


# -- Entity selection present_count --


def test_entity_selection_present_count_punned_entity(ont):
    # A punned entity has two Declaration axioms (Class + NamedIndividual).
    # present_count must be 1 (one entity in the selection), not 2.
    from ontoloom.ontology.models.axioms import Declaration

    axioms.add(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Pun")),
            Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI("ex:Pun")),
        ],
    )
    selections.upsert(ont, "punned", SelectionKind.ENTITIES, ["ex:Pun"], "test")

    page = selections.read(ont, "punned")
    assert page.present >= 0
    assert page.missing >= 0
    assert page.present + page.missing == page.meta.cardinality


# -- LockedSelection minimum prefix length --


def test_locked_selection_min_prefix_length():
    import pytest

    for short in ("a", "ab", "abcdefg"):
        with pytest.raises(ValueError, match="at least 8"):
            LockedSelection(f"sel@{short}")

    # 8 chars is the minimum — must not raise
    LockedSelection("sel@abcdef01")
    LockedSelection("sel@" + "a" * 16)


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
    prefixes.set_prefix(ont, "ex", "http://example.org/")
    prefixes.set_prefix(ont, "rdfs", "http://www.w3.org/2000/01/rdf-schema#")
    assert prefixes.list_all(ont) == {
        "ex": "http://example.org/",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    }


def test_set_prefix_overwrites(ont):
    prefixes.set_prefix(ont, "ex", "http://example.org/v1/")
    prefixes.set_prefix(ont, "ex", "http://example.org/v2/")
    assert prefixes.list_all(ont)["ex"] == "http://example.org/v2/"


def test_remove_prefix(ont):
    prefixes.set_prefix(ont, "ex", "http://example.org/")
    prefixes.set_prefix(ont, "rdfs", "http://www.w3.org/2000/01/rdf-schema#")
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
    assert len(lines) == 9  # 1 header + 8 axioms

    header = json.loads(lines[0])
    assert header["format"] == "ontoloom-jsonl"
    assert "format_version" in header

    for line in lines[1:]:
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
    subclassof_hash = next(ha.hash for ha in result.added if ha.axiom.type_ == "SubClassOf")
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
    from ontoloom.ontology.errors import EntityNotFoundError

    with pytest.raises(EntityNotFoundError):
        entities.get(ont, IRI("ex:NonExistent"))


def test_get_entity_not_found_includes_near_matches(populated):
    from ontoloom.ontology.errors import EntityNotFoundError

    # Local-name substring "Anim" matches "Animal".
    with pytest.raises(EntityNotFoundError) as exc_info:
        entities.get(populated, IRI("ex:Anim"))
    assert any("Animal" in m for m in exc_info.value.near_matches)


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
    from ontoloom.ontology.export import HeaderRecord, import_jsonl

    export_path = tmp_path / "roundtrip.jsonl"
    export.to_jsonl(populated, export_path)

    imported = import_jsonl(export_path)
    assert isinstance(imported.header, HeaderRecord)
    assert imported.header.format == "ontoloom-jsonl"
    assert len(imported.axioms) == 8
    for axiom in imported.axioms:
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
    selections.upsert(ont, "audit_one", SelectionKind.ENTITIES, ["ex:Dog"], "test")
    selections.upsert(ont, "audit_two", SelectionKind.ENTITIES, ["ex:Dog"], "test")
    selections.upsert(ont, "keep", SelectionKind.ENTITIES, ["ex:Dog"], "test")

    dropped = selections.remove_by_pattern(ont, "audit_*")
    names = [d.name for d in dropped]
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


def test_workspace_root_blocks_outside(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.db"
    Ontology.create(outside)

    monkeypatch.setattr("ontoloom.ontology.connection.WORKSPACE_ROOT", workspace.resolve())
    from ontoloom.ontology.errors import BadRequestError

    with pytest.raises(BadRequestError, match="outside the configured workspace"):
        Ontology(outside)
    with pytest.raises(BadRequestError, match="outside the configured workspace"):
        Ontology.create(workspace.parent / "another.db")


def test_workspace_root_allows_inside(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr("ontoloom.ontology.connection.WORKSPACE_ROOT", workspace.resolve())

    inside = workspace / "ok.db"
    Ontology.create(inside)
    with Ontology(inside) as ont:
        assert ont.conn is not None


def test_workspace_root_unset_unrestricted(tmp_path, monkeypatch):
    monkeypatch.setattr("ontoloom.ontology.connection.WORKSPACE_ROOT", None)
    path = tmp_path / "anywhere.db"
    Ontology.create(path)
    with Ontology(path) as ont:
        assert ont.conn is not None


def test_open_non_ontoloom_db_raises(tmp_path):
    import sqlite3

    path = tmp_path / "other.db"
    conn = sqlite3.connect(str(path), autocommit=True)
    conn.execute("CREATE TABLE foo (id INTEGER)")
    conn.close()

    with pytest.raises(OntologySchemaError), Ontology(path):
        pass


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
    selections.upsert(ont, "ax_sel", SelectionKind.AXIOMS, hashes, "test")
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
    prefixes.set_prefix(ont, "ex", "http://example.org/")
    prefixes.set_prefix(ont, "other", "http://other.org/")
    prefixes.set_prefix(ont, "unused", "http://unused.org/")

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


# -- P-03-5: AmbiguousHashError and StoreCorruptionError --


def test_ambiguous_hash_error(ont):
    prefix = "aaaa"
    h1 = prefix + "0" * 60
    h2 = prefix + "1" + "0" * 59
    with ont.conn:
        ont.conn.execute(
            "INSERT INTO axioms (hash, type, data) VALUES (?, 'Declaration', jsonb(?))",
            (h1, '{"type":"Declaration","iri":"ex:X","entity_type":"Class","annotations":[]}'),
        )
        ont.conn.execute(
            "INSERT INTO axioms (hash, type, data) VALUES (?, 'Declaration', jsonb(?))",
            (h2, '{"type":"Declaration","iri":"ex:Y","entity_type":"Class","annotations":[]}'),
        )

    with pytest.raises(AmbiguousHashError) as exc_info:
        axioms.remove_by_hash(ont, [prefix])
    assert exc_info.value.count == 2
    assert exc_info.value.prefix == prefix


def test_store_corruption_error(ont):
    h = "b" * 64
    with ont.conn:
        ont.conn.execute(
            "INSERT INTO axioms (hash, type, data) VALUES (?, 'Unknown', jsonb(?))",
            (h, '{"type":"UnknownAxiomType","garbage":true}'),
        )

    row = ont.conn.execute("SELECT json(data) FROM axioms WHERE hash = ?", (h,)).fetchone()
    assert row is not None
    with pytest.raises(StoreCorruptionError):
        load_axiom(row[0], "test context")


# -- P-03-6: JSONL export round-trip --


def test_export_jsonl_hash_roundtrip(populated, tmp_path):
    original_hashes = {r[0] for r in populated.conn.execute("SELECT hash FROM axioms")}

    export_path = tmp_path / "export.jsonl"
    export.to_jsonl(populated, export_path)

    lines = export_path.read_text().strip().split("\n")
    adapter = TypeAdapter(Axiom)
    for line in lines[1:]:  # skip header
        parsed = adapter.validate_json(line)
        assert axiom_hash(parsed) in original_hashes


def test_export_jsonl_byte_identical(populated, tmp_path):
    p1 = tmp_path / "a.jsonl"
    p2 = tmp_path / "b.jsonl"
    export.to_jsonl(populated, p1)
    export.to_jsonl(populated, p2)
    # Header lines differ (exported_at timestamp); axiom lines must be deterministic.
    axiom_lines_1 = p1.read_text().splitlines()[1:]
    axiom_lines_2 = p2.read_text().splitlines()[1:]
    assert axiom_lines_1 == axiom_lines_2


# -- P-03-7: rename_iri edge cases --


def test_rename_iri_noop_same_iri(ont):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    axioms.add(ont, [ax])
    h = axiom_hash(ax)

    result = axioms.rename_iri(ont, "ex:Dog", "ex:Dog")
    assert len(result.replaced) == 1
    assert result.replaced[0].was_noop is True
    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h,)).fetchone() is not None


def test_rename_iri_collision_with_existing(ont):
    ax_old = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal"))
    ax_new = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mammal"))
    axioms.add(ont, [ax_old, ax_new])
    old_h = axiom_hash(ax_old)
    new_h = axiom_hash(ax_new)

    result = axioms.rename_iri(ont, "ex:Animal", "ex:Mammal")
    assert len(result.replaced) == 1
    assert not result.replaced[0].was_noop

    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (old_h,)).fetchone() is None
    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (new_h,)).fetchone() is not None


def test_rename_iri_scoped_to_selection(ont):
    ax_in = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    ax_out = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Cat")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    result = axioms.add(ont, [ax_in, ax_out])
    h_in = next(ha.hash for ha in result.added if ha.axiom == ax_in)
    h_out = axiom_hash(ax_out)

    sel_hash = selections.upsert(ont, "scope", SelectionKind.AXIOMS, [h_in], "test").content_hash
    locked = LockedSelection(f"scope@{sel_hash[:8]}")

    renamed = axioms.rename_iri(ont, "ex:Animal", "ex:Mammal", within=locked)
    assert len(renamed.replaced) == 1

    # ax_out is outside the scope — its hash should be unchanged
    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h_out,)).fetchone() is not None


# -- P-03-11: Additional small coverage gaps --


def test_replace_to_existing_hash(ont):
    ax_a = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    ax_b = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Mammal")),
    )
    axioms.add(ont, [ax_a, ax_b])
    h_a = axiom_hash(ax_a)
    h_b = axiom_hash(ax_b)

    result = axioms.replace(ont, h_a[:8], ax_b)
    assert not result.was_noop
    assert result.new_hash == h_b

    # Old axiom gone; new (pre-existing) axiom survives unmodified
    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h_a,)).fetchone() is None
    assert ont.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h_b,)).fetchone() is not None


def test_prefix_remove_while_in_use(ont):
    prefixes.set_prefix(ont, "ex", "http://example.org/")
    axioms.add(ont, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])

    with pytest.raises(BadRequestError, match="Cannot remove prefix"):
        prefixes.remove(ont, "ex")

    assert "ex" in prefixes.list_all(ont)


def test_find_duplicates_tie_break_order(ont):
    axioms.add(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:D")),
            AnnotationAssertion(
                property=IRI("rdfs:label"), subject=IRI("ex:A"), value=LangLiteral(value="Alpha")
            ),
            AnnotationAssertion(
                property=IRI("rdfs:label"), subject=IRI("ex:B"), value=LangLiteral(value="Alpha")
            ),
            AnnotationAssertion(
                property=IRI("rdfs:label"), subject=IRI("ex:C"), value=LangLiteral(value="Beta")
            ),
            AnnotationAssertion(
                property=IRI("rdfs:label"), subject=IRI("ex:D"), value=LangLiteral(value="Beta")
            ),
        ],
    )

    result = entities.find_duplicates(ont, "rdfs:label")
    assert result.total_groups == 2
    # Groups have equal count; stable sort preserves SQL text order → "Alpha" < "Beta"
    assert [g.value for g in result.groups] == ["Alpha", "Beta"]


def test_unicode_iri_roundtrip(ont, tmp_path):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Ångström"))
    axioms.add(ont, [ax])
    h = axiom_hash(ax)

    export_path = tmp_path / "uni.jsonl"
    export.to_jsonl(ont, export_path)

    adapter = TypeAdapter(Axiom)
    lines = export_path.read_text().strip().split("\n")
    parsed = adapter.validate_json(lines[1])  # lines[0] is the header
    assert axiom_hash(parsed) == h


def test_has_key_neither_properties_rejected():
    with pytest.raises(ValueError, match="at least one"):
        HasKey(
            class_expression=NamedClass(iri=IRI("ex:Person")),
            object_properties=(),
            data_properties=(),
        )


def test_list_all_selections_order(ont):
    # Force identical created_at on two selections; tiebreaker by name must sort a_sel first.
    selections.upsert(ont, "z_sel", SelectionKind.ENTITIES, ["ex:A"], "test")
    selections.upsert(ont, "a_sel", SelectionKind.ENTITIES, ["ex:B"], "test")
    ont.conn.execute("UPDATE selections SET created_at = '2026-04-30T12:00:00.000Z'")

    names = [s.name for s in selections.list_all(ont)]
    assert names == ["a_sel", "z_sel"]


def test_show_changes_sequence_id_order(ont):
    ax1 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A"))
    ax2 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B"))
    axioms.add(ont, [ax1])
    axioms.add(ont, [ax2])

    from ontoloom.ontology.history import show_changes

    events = show_changes(ont)
    assert len(events) >= 2
    seq_ids = [e.sequence_id for e in events]
    assert seq_ids == sorted(seq_ids)
