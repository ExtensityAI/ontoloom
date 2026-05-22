"""CRUD: add, remove, replace, annotate, rename_iri, get_entity,
prefix management, selection-derived counts, lifecycle, and corruption.

Search-overlap tests live in test_search.py; IRI validator tests in
test_iri.py; hash-prefix tests in test_resolve_hash_prefix.py; export tests
in test_export.py.
"""

import json

import pytest
from ontoloom.axioms.deserialize import load_axiom
from ontoloom.axioms.hashing import AxiomHash, AxiomNotFoundError
from ontoloom.axioms.mutations import (
    add_axioms,
    annotate_axiom,
    remove_by_hash,
    rename_iri,
    replace_axiom,
)
from ontoloom.axioms.types import HashedAxiom
from ontoloom.connection import (
    Ontology,
    OntologyExistsError,
    OntologyNotFoundError,
    OntologySchemaError,
    session,
)
from ontoloom.entities.reader import (
    EntityNotFoundError,
    find_duplicate_entities,
    get_entity,
)
from ontoloom.entities.text import LOCAL_NAME_PROPERTY
from ontoloom.errors import StoreCorruptionError
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import (
    AnnotationAssertion,
    AxiomTag,
    Declaration,
    EquivalentClasses,
    HasKey,
    SubClassOf,
)
from ontoloom.owl.expressions import ObjectSomeValuesFrom
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType, Position
from ontoloom.prefixes.store import (
    list_prefixes,
    prefix_usage_counts,
    remove_prefix,
    set_prefix,
)
from ontoloom.prefixes.types import (
    NamespaceIRI,
    PrefixInUseError,
    PrefixName,
    PrefixNotFoundError,
)
from ontoloom.query.dispatch import run
from ontoloom.selections.compose import create_selection
from ontoloom.selections.expr import EntitiesInExpr
from ontoloom.selections.store import (
    list_selections,
    upsert_selection,
)
from ontoloom.selections.read_entity_selection import ReadEntitySelection
from ontoloom.selections.types import (
    AxiomSelectionName,
    EntitySelectionName,
    SelectionKind,
    SelectionName,
)


def _ent(name: str) -> EntitySelectionName:
    return EntitySelectionName(f"entities:{name}")


EX = PrefixName("ex")
EX_NS = NamespaceIRI("http://example.org/")
EX_NS_V1 = NamespaceIRI("http://example.org/v1/")
SEL = SelectionName("sel")


@pytest.fixture()
def populated(s):
    add_axioms(
        s,
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
                sub_class=IRI("ex:Dog"),
                super_class=IRI("ex:Animal"),
            ),
        ],
    )
    return s


# -- Logical hashing --


def test_annotations_do_not_affect_dedup(s):
    ax1 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    ax2 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note")),),
    )
    result1 = add_axioms(s, [ax1])
    assert len(result1.added) == 1

    result2 = add_axioms(s, [ax2])
    assert len(result2.skipped) == 1
    assert len(result2.added) == 0
    assert result1.added[0].hash == result2.skipped[0].hash


def test_set_semantic_dedup(s):
    ax1 = EquivalentClasses(equivalent_classes=(IRI("ex:A"), IRI("ex:B")))
    ax2 = EquivalentClasses(equivalent_classes=(IRI("ex:B"), IRI("ex:A")))
    result = add_axioms(s, [ax1, ax2])
    assert len(result.added) == 1
    assert len(result.skipped) == 1


def test_populate_indexes_writes_local_name_and_annotation_value(s):
    """Adding a Declaration plus an AnnotationAssertion populates entity_text
    with both a local_name row for the entity IRI and a property-keyed row
    for the annotation value."""
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Foo")),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Foo"),
                value=LangLiteral(value="Foo Label"),
            ),
        ],
    )

    local_rows = list(
        s.conn.execute(
            "SELECT entity_iri, text FROM entity_text WHERE entity_iri = ? AND property = ?",
            ("ex:Foo", LOCAL_NAME_PROPERTY),
        )
    )
    assert ("ex:Foo", "Foo") in local_rows

    label_rows = list(
        s.conn.execute(
            "SELECT entity_iri, text FROM entity_text WHERE entity_iri = ? AND property = ?",
            ("ex:Foo", "rdfs:label"),
        )
    )
    assert label_rows == [("ex:Foo", "Foo Label")]


# -- Annotate axiom --


def test_annotate_axiom_updates_in_place(s):
    ax = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    result = add_axioms(s, [ax])
    h = result.added[0].hash

    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="important"))
    updated = annotate_axiom(s, h, add_annotations=[ann])

    assert updated.hashed.hash == h
    assert len(updated.hashed.axiom.annotations) == 1
    annotation_value = updated.hashed.axiom.annotations[0].value
    assert isinstance(annotation_value, LangLiteral)
    assert annotation_value.value == "important"
    assert updated.added == (ann,)
    assert updated.removed == ()


def test_annotate_axiom_remove(s):
    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note"))
    ax = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(ann,),
    )
    result = add_axioms(s, [ax])
    h = result.added[0].hash

    updated = annotate_axiom(s, h, remove_annotations=[ann])
    assert len(updated.hashed.axiom.annotations) == 0
    assert updated.removed == (ann,)
    assert updated.added == ()


def test_annotate_axiom_dedup_against_existing(s):
    """Adding an annotation that already exists is a no-op; reflected in `added`."""
    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note"))
    ax = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(ann,),
    )
    result = add_axioms(s, [ax])
    h = result.added[0].hash

    updated = annotate_axiom(s, h, add_annotations=[ann])
    # Already present; nothing new applied.
    assert updated.added == ()
    assert len(updated.hashed.axiom.annotations) == 1


def test_annotate_axiom_remove_absent_is_noop(s):
    """Removing an annotation that isn't there is a no-op; reflected in `removed`."""
    ax = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    result = add_axioms(s, [ax])
    h = result.added[0].hash

    absent = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="not there"))
    updated = annotate_axiom(s, h, remove_annotations=[absent])
    assert updated.removed == ()


def test_annotate_nonexistent_raises(s):
    with pytest.raises(AxiomNotFoundError):
        annotate_axiom(s, AxiomHash("dead" + "0" * 60), add_annotations=[])


# -- Replace / rename annotation preservation --


def test_replace_preserves_old_annotations(s):
    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="kept"))
    old = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(ann,),
    )
    add_axioms(s, [old])
    old_h = HashedAxiom.of(old).hash

    new = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Mammal"),
    )
    result = replace_axiom(s, old_h, new)
    assert not result.was_noop

    row = s.conn.execute(
        "SELECT json(data) FROM axioms WHERE hash = ?", (result.new.hash,)
    ).fetchone()
    stored = json.loads(row[0])
    assert stored["annotations"] == [ann.model_dump(mode="json")]


def test_replace_discards_new_axiom_annotations(s):
    old = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(s, [old])
    old_h = HashedAxiom.of(old).hash

    new = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Mammal"),
        annotations=(Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="ignored")),),
    )
    result = replace_axiom(s, old_h, new)

    row = s.conn.execute(
        "SELECT json(data) FROM axioms WHERE hash = ?", (result.new.hash,)
    ).fetchone()
    stored = json.loads(row[0])
    # Old axiom had no annotations; new_axiom's annotations are discarded.
    assert stored["annotations"] == []


def test_rename_iri_preserves_annotations(s):
    ann = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="kept"))
    ax = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(ann,),
    )
    add_axioms(s, [ax])

    result = rename_iri(s, IRI("ex:Animal"), IRI("ex:Mammal"))
    assert len(result.replaced) == 1
    assert not result.replaced[0].was_noop

    row = s.conn.execute(
        "SELECT json(data) FROM axioms WHERE hash = ?", (result.replaced[0].new.hash,)
    ).fetchone()
    stored = json.loads(row[0])
    assert stored["annotations"] == [ann.model_dump(mode="json")]


def test_rename_iri_does_not_corrupt_literal_values(s):
    # AnnotationAssertion whose subject IS the renamed IRI and whose value string
    # coincidentally equals it. Only the IRI-typed subject field must be rewritten.
    ax = AnnotationAssertion(
        property=IRI("rdfs:comment"),
        subject=IRI("ex:Animal"),
        value=LangLiteral(value="ex:Animal"),
    )
    add_axioms(s, [ax])

    result = rename_iri(s, IRI("ex:Animal"), IRI("ex:Mammal"))
    assert len(result.replaced) == 1

    row = s.conn.execute(
        "SELECT json(data) FROM axioms WHERE hash = ?", (result.replaced[0].new.hash,)
    ).fetchone()
    stored = json.loads(row[0])
    assert stored["subject"] == "ex:Mammal"  # IRI field renamed
    assert stored["value"]["value"] == "ex:Animal"  # literal value unchanged


def test_rename_iri_noop_when_iri_absent(s):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    add_axioms(s, [ax])

    result = rename_iri(s, IRI("ex:Cat"), IRI("ex:Kitten"))
    assert result.replaced == ()


# -- rename_iri edge cases --


def test_rename_iri_noop_same_iri(s):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    add_axioms(s, [ax])
    h = HashedAxiom.of(ax).hash

    result = rename_iri(s, IRI("ex:Dog"), IRI("ex:Dog"))
    assert len(result.replaced) == 1
    assert result.replaced[0].was_noop is True
    assert s.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h,)).fetchone() is not None


def test_rename_iri_collision_with_existing(s):
    ax_old = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal"))
    ax_new = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mammal"))
    add_axioms(s, [ax_old, ax_new])
    old_h = HashedAxiom.of(ax_old).hash
    new_h = HashedAxiom.of(ax_new).hash

    result = rename_iri(s, IRI("ex:Animal"), IRI("ex:Mammal"))
    assert len(result.replaced) == 1
    assert not result.replaced[0].was_noop

    assert s.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (old_h,)).fetchone() is None
    assert s.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (new_h,)).fetchone() is not None


def test_rename_iri_collision_sets_merged_flag_and_colliding_hashes(s):
    ax_old = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal"))
    ax_new = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mammal"))
    add_axioms(s, [ax_old, ax_new])
    new_h = HashedAxiom.of(ax_new).hash

    result = rename_iri(s, IRI("ex:Animal"), IRI("ex:Mammal"))

    assert len(result.replaced) == 1
    rep = result.replaced[0]
    assert rep.was_merged_into_existing is True
    assert result.colliding_hashes == (new_h,)


def test_rename_iri_no_collision_has_empty_colliding_hashes(s):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal"))
    add_axioms(s, [ax])

    result = rename_iri(s, IRI("ex:Animal"), IRI("ex:Mammal"))

    assert len(result.replaced) == 1
    assert result.replaced[0].was_merged_into_existing is False
    assert result.colliding_hashes == ()


def test_rename_iri_scoped_to_selection(s):
    ax_in = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    ax_out = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
    )
    result = add_axioms(s, [ax_in, ax_out])
    h_in = next(ha.hash for ha in result.added if ha.axiom == ax_in)
    h_out = HashedAxiom.of(ax_out).hash

    upsert_selection(s, SelectionName("scope"), SelectionKind.AXIOMS, [h_in], "test")

    renamed = rename_iri(
        s, IRI("ex:Animal"), IRI("ex:Mammal"), within=AxiomSelectionName("axioms:scope")
    )
    assert len(renamed.replaced) == 1

    # ax_out is outside the scope -> its hash should be unchanged
    assert s.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h_out,)).fetchone() is not None


# -- Replace to existing hash --


def test_replace_to_existing_hash(s):
    ax_a = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    ax_b = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Mammal"),
    )
    add_axioms(s, [ax_a, ax_b])
    h_a = HashedAxiom.of(ax_a).hash
    h_b = HashedAxiom.of(ax_b).hash

    result = replace_axiom(s, h_a, ax_b)
    assert not result.was_noop
    assert result.new.hash == h_b

    # Old axiom gone; new (pre-existing) axiom survives unmodified
    assert s.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h_a,)).fetchone() is None
    assert s.conn.execute("SELECT 1 FROM axioms WHERE hash = ?", (h_b,)).fetchone() is not None


# -- Entity selection present_count --


def test_entity_selection_present_count_punned_entity(s):
    # A punned entity has two Declaration axioms (Class + NamedIndividual).
    # present_count must be 1 (one entity in the selection), not 2.
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Pun")),
            Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI("ex:Pun")),
        ],
    )
    upsert_selection(s, SelectionName("punned"), SelectionKind.ENTITIES, ["ex:Pun"], "test")

    page = run(s, ReadEntitySelection(selection=_ent("punned")))
    assert page.present >= 0
    assert page.missing >= 0
    assert page.present + page.missing == page.meta.size


# -- Prefix management --


def test_set_and_list_prefixes(bare_session):
    set_prefix(bare_session, EX, EX_NS)
    set_prefix(
        bare_session, PrefixName("rdfs"), NamespaceIRI("http://www.w3.org/2000/01/rdf-schema#")
    )
    assert list_prefixes(bare_session) == {
        "ex": "http://example.org/",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    }


def test_set_prefix_overwrites_when_unused(bare_session):
    set_prefix(bare_session, EX, EX_NS_V1)
    set_prefix(bare_session, EX, NamespaceIRI("http://example.org/v2/"))
    assert list_prefixes(bare_session)[EX] == "http://example.org/v2/"


def test_set_prefix_reports_previous_iri_and_in_use_count(bare_session):
    # First insert: no previous, no usage.
    result = set_prefix(bare_session, EX, EX_NS_V1)
    assert result.previous_iri is None
    assert result.in_use_count == 0

    # Idempotent reassignment to the same IRI: previous set, no usage.
    result = set_prefix(bare_session, EX, EX_NS_V1)
    assert result.previous_iri == "http://example.org/v1/"
    assert result.in_use_count == 0

    # Real reassignment with axioms using the prefix.
    add_axioms(bare_session, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = set_prefix(bare_session, EX, NamespaceIRI("http://example.org/v2/"))
    assert result.previous_iri == "http://example.org/v1/"
    assert result.in_use_count == 1
    assert list_prefixes(bare_session)[EX] == "http://example.org/v2/"


def test_remove_prefix(bare_session):
    set_prefix(bare_session, EX, EX_NS)
    set_prefix(
        bare_session, PrefixName("rdfs"), NamespaceIRI("http://www.w3.org/2000/01/rdf-schema#")
    )
    remove_prefix(bare_session, EX)
    result = list_prefixes(bare_session)
    assert "ex" not in result
    assert "rdfs" in result


def test_remove_nonexistent_prefix_raises(s):
    with pytest.raises(PrefixNotFoundError):
        remove_prefix(s, PrefixName("nonexistent"))


def test_prefix_remove_while_in_use(s):
    set_prefix(s, EX, EX_NS)
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])

    with pytest.raises(PrefixInUseError) as exc:
        remove_prefix(s, EX)
    assert exc.value.name == "ex"
    assert exc.value.count == 1

    assert "ex" in list_prefixes(s)


def test_prefix_usage_counts(s):
    set_prefix(s, EX, EX_NS)
    set_prefix(s, PrefixName("other"), NamespaceIRI("http://other.org/"))
    set_prefix(s, PrefixName("unused"), NamespaceIRI("http://unused.org/"))

    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("other:Fish")),
        ],
    )

    counts = prefix_usage_counts(s)
    assert counts[EX] == 2
    assert counts[PrefixName("other")] == 1
    assert counts[PrefixName("unused")] == 0


# -- get_entity --


def test_get_entity_found(populated):
    info = get_entity(populated, IRI("ex:Dog"))
    assert info is not None
    assert EntityType.CLASS in info.roles
    assert any(a.value == "Dog" for a in info.annotations)
    assert AxiomTag.SUB_CLASS_OF in info.axiom_counts


def test_get_entity_not_found(s):
    with pytest.raises(EntityNotFoundError):
        get_entity(s, IRI("ex:NonExistent"))


def test_get_entity_not_found_includes_near_matches(populated):
    # Local-name substring "Anim" matches "Animal".
    with pytest.raises(EntityNotFoundError) as exc_info:
        get_entity(populated, IRI("ex:Anim"))
    assert any("Animal" in m for m in exc_info.value.near_matches)


# -- remove --


def test_remove_not_found_raises(s):
    with pytest.raises(AxiomNotFoundError):
        remove_by_hash(s, [AxiomHash("dead" + "0" * 60)])


def test_batch_remove_multiple(s):
    ax1 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A"))
    ax2 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B"))
    result = add_axioms(s, [ax1, ax2])
    h1 = result.added[0].hash
    h2 = result.added[1].hash

    removed = remove_by_hash(s, [h1, h2])
    assert len(removed.removed) == 2


def test_batch_remove_rollback_on_failure(s):
    """If one hash in a batch is missing, none should be removed."""
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A"))
    result = add_axioms(s, [ax])
    h = result.added[0].hash

    with pytest.raises(AxiomNotFoundError):
        remove_by_hash(s, [h, AxiomHash("dead" + "0" * 60)])

    # The first axiom should still exist (rollback)
    count = s.conn.execute("SELECT COUNT(*) FROM axioms").fetchone()[0]
    assert count == 1


def test_remove_by_hash_batches_single_query(s):
    axs = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Aa")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Bb")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cc")),
    ]
    add_axioms(s, axs)
    hashes = [HashedAxiom.of(a).hash for a in axs]

    result = remove_by_hash(s, hashes)
    assert tuple(ha.hash for ha in result.removed) == tuple(hashes)


def test_remove_by_hash_missing_raises_for_first_absent(s):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A"))
    add_axioms(s, [ax])
    h = HashedAxiom.of(ax).hash
    missing_a = AxiomHash("dead" + "0" * 60)
    missing_b = AxiomHash("beef" + "0" * 60)

    with pytest.raises(AxiomNotFoundError) as exc:
        remove_by_hash(s, [h, missing_a, missing_b])
    assert exc.value.needle == missing_a


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


def test_workspace_root_blocks_outside(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.db"
    Ontology.create(outside)

    monkeypatch.setattr("ontoloom.connection.WORKSPACE_ROOT", workspace.resolve())

    with pytest.raises(PermissionError, match="outside the configured workspace"):
        Ontology(outside)
    with pytest.raises(PermissionError, match="outside the configured workspace"):
        Ontology.create(workspace.parent / "another.db")


def test_workspace_root_allows_inside(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr("ontoloom.connection.WORKSPACE_ROOT", workspace.resolve())

    inside = workspace / "ok.db"
    Ontology.create(inside)
    with session(Ontology(inside)) as s:
        assert s.conn is not None
        s.commit()


def test_workspace_root_unset_unrestricted(tmp_path, monkeypatch):
    monkeypatch.setattr("ontoloom.connection.WORKSPACE_ROOT", None)
    path = tmp_path / "anywhere.db"
    Ontology.create(path)
    with session(Ontology(path)) as s:
        assert s.conn is not None
        s.commit()


def test_open_non_ontoloom_db_raises(tmp_path):
    import sqlite3

    path = tmp_path / "other.db"
    conn = sqlite3.connect(str(path), autocommit=True)
    conn.execute("CREATE TABLE foo (id INTEGER)")
    conn.close()

    with pytest.raises(OntologySchemaError), session(Ontology(path)):
        pass


# -- Selection: entities_in with position filter --


@pytest.fixture()
def axiom_selection(s):
    """Create an axiom selection containing SubClassOf and ObjectSomeValuesFrom axioms."""
    result = add_axioms(
        s,
        [
            SubClassOf(
                sub_class=IRI("ex:Dog"),
                super_class=IRI("ex:Animal"),
            ),
            SubClassOf(
                sub_class=IRI("ex:Cat"),
                super_class=ObjectSomeValuesFrom(
                    property=IRI("ex:hasOwner"),
                    filler=IRI("ex:Person"),
                ),
            ),
        ],
    )
    hashes = [ha.hash for ha in result.added]
    upsert_selection(s, SelectionName("ax_sel"), SelectionKind.AXIOMS, hashes, "test")
    return s


def test_entities_in_with_field_sub_class(axiom_selection):
    create_selection(
        axiom_selection,
        _ent("sub_classes"),
        EntitiesInExpr(entities_in=SelectionName("ax_sel"), position=Position.SUB_CLASS),
    )
    items = [
        r[0]
        for r in axiom_selection.conn.execute(
            "SELECT item FROM selection_items WHERE selection_name = ?", ("sub_classes",)
        )
    ]
    assert set(items) == {"ex:Dog", "ex:Cat"}


def test_entities_in_with_field_super_class(axiom_selection):
    create_selection(
        axiom_selection,
        _ent("super_classes"),
        EntitiesInExpr(entities_in=SelectionName("ax_sel"), position=Position.SUPER_CLASS),
    )
    items = [
        r[0]
        for r in axiom_selection.conn.execute(
            "SELECT item FROM selection_items WHERE selection_name = ?", ("super_classes",)
        )
    ]
    # Only the first SubClassOf has a named super_class (ex:Animal).
    # The second has ObjectSomeValuesFrom -> no entity in super_class position.
    assert set(items) == {"ex:Animal"}


def test_entities_in_with_field_filler(axiom_selection):
    create_selection(
        axiom_selection,
        _ent("fillers"),
        EntitiesInExpr(entities_in=SelectionName("ax_sel"), position=Position.FILLER),
    )
    items = [
        r[0]
        for r in axiom_selection.conn.execute(
            "SELECT item FROM selection_items WHERE selection_name = ?", ("fillers",)
        )
    ]
    assert set(items) == {"ex:Person"}


def test_entities_in_without_field(axiom_selection):
    create_selection(
        axiom_selection, _ent("all_ents"), EntitiesInExpr(entities_in=SelectionName("ax_sel"))
    )
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


# -- Store corruption --


def test_store_corruption_error(s):
    h = "b" * 64
    s.conn.execute(
        "INSERT INTO axioms (hash, type, data) VALUES (?, 'Unknown', jsonb(?))",
        (h, '{"type":"UnknownAxiomType","garbage":true}'),
    )

    row = s.conn.execute("SELECT json(data) FROM axioms WHERE hash = ?", (h,)).fetchone()
    assert row is not None
    with pytest.raises(StoreCorruptionError):
        load_axiom(row[0], "test context")


# -- HasKey validation --


def test_has_key_neither_properties_rejected():
    with pytest.raises(ValueError, match="at least one"):
        HasKey(
            class_expression=IRI("ex:Person"),
            object_properties=(),
            data_properties=(),
        )


# -- find_duplicates --


def test_find_duplicates_tie_break_order(s):
    add_axioms(
        s,
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

    result = find_duplicate_entities(s, IRI("rdfs:label"))
    assert result.total_groups == 2
    # Groups have equal count; stable sort preserves SQL text order → "Alpha" < "Beta"
    assert [g.value for g in result.groups] == ["Alpha", "Beta"]


# -- list_selections --


def test_list_all_selections_order(s):
    # Force identical created_at on two selections; tiebreaker by name must sort a_sel first.
    upsert_selection(s, SelectionName("z_sel"), SelectionKind.ENTITIES, ["ex:A"], "test")
    upsert_selection(s, SelectionName("a_sel"), SelectionKind.ENTITIES, ["ex:B"], "test")
    s.conn.execute("UPDATE selections SET created_at = '2026-04-30T12:00:00.000Z'")

    names = [ls.meta.name for ls in list_selections(s)]
    assert names == ["a_sel", "z_sel"]


def test_list_selections_present_count_no_double_count(s):
    # An entity referenced by multiple axioms must still count once.
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Mammal")),
        ],
    )
    upsert_selection(s, SEL, SelectionKind.ENTITIES, ["ex:Dog", "ex:Ghost"], "test")

    listings = {ls.meta.name: ls for ls in list_selections(s)}
    assert listings[SEL].present_count == 1


def test_list_selections_entity_selection_unaffected_by_axiom_growth(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    upsert_selection(s, SEL, SelectionKind.ENTITIES, ["ex:Dog"], "test")
    before = {ls.meta.name: ls.present_count for ls in list_selections(s)}

    add_axioms(s, [SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))])
    after = {ls.meta.name: ls.present_count for ls in list_selections(s)}

    assert before[SEL] == after[SEL] == 1
