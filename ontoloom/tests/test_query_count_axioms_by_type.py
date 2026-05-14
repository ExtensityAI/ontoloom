"""Tests for the CountAxiomsByType query and the shared `_axiom_predicates` helper."""

from collections import Counter

from ontoloom.axioms.store import add_axioms
from ontoloom.hashing import HashedAxiom
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query._constraints import (
    AlwaysFalse,
    InSelection,
    MentionsAll,
    MentionsAny,
    OfTypes,
)
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.query.count_axioms_by_type import CountAxiomsByType, _run, render
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import SelectionKind, SelectionName

# -- render snapshots: no DB --


def test_render_no_constraints():
    compiled = render(CountAxiomsByType(constraints=()))
    assert compiled.sql == "SELECT a.type, COUNT(*) FROM axioms a GROUP BY a.type"
    assert compiled.params == ()


def test_render_of_types_single():
    compiled = render(CountAxiomsByType(constraints=(OfTypes(tags=("Declaration",)),)))
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE a.type IN (?) GROUP BY a.type"
    )
    assert compiled.params == ("Declaration",)


def test_render_of_types_many():
    compiled = render(CountAxiomsByType(constraints=(OfTypes(tags=("SubClassOf", "Declaration")),)))
    # tags are deduped and sorted by the field validator.
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE a.type IN (?,?) GROUP BY a.type"
    )
    assert compiled.params == ("Declaration", "SubClassOf")


def test_render_mentions_all_single():
    compiled = render(CountAxiomsByType(constraints=(MentionsAll(iris=(IRI("ex:A"),)),)))
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri = ?) "
        "GROUP BY a.type"
    )
    assert compiled.params == ("ex:A",)


def test_render_mentions_all_multi_emits_one_exists_per_iri():
    compiled = render(
        CountAxiomsByType(constraints=(MentionsAll(iris=(IRI("ex:B"), IRI("ex:A"))),))
    )
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri = ?) AND "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri = ?) "
        "GROUP BY a.type"
    )
    # dedupe_sort sorts the iris.
    assert compiled.params == ("ex:A", "ex:B")


def test_render_mentions_any_single():
    compiled = render(CountAxiomsByType(constraints=(MentionsAny(iris=(IRI("ex:A"),)),)))
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri IN (?)) "
        "GROUP BY a.type"
    )
    assert compiled.params == ("ex:A",)


def test_render_mentions_any_many():
    compiled = render(
        CountAxiomsByType(constraints=(MentionsAny(iris=(IRI("ex:B"), IRI("ex:A"))),))
    )
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri IN (?,?)) "
        "GROUP BY a.type"
    )
    assert compiled.params == ("ex:A", "ex:B")


def test_render_in_selection_axioms():
    ref = ResolvedSelection(kind=SelectionKind.AXIOMS, bare_name="my_axiom_sel")
    compiled = render(CountAxiomsByType(constraints=(InSelection(ref=ref),)))
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM selection_items si_w "
        "WHERE si_w.item = a.hash AND si_w.selection_name = ?) "
        "GROUP BY a.type"
    )
    assert compiled.params == ("my_axiom_sel",)


def test_render_in_selection_entities():
    ref = ResolvedSelection(kind=SelectionKind.ENTITIES, bare_name="my_entity_sel")
    compiled = render(CountAxiomsByType(constraints=(InSelection(ref=ref),)))
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_w "
        "WHERE ae_w.axiom_id = a.id "
        "AND EXISTS (SELECT 1 FROM selection_items si_w "
        "WHERE si_w.item = ae_w.entity_iri AND si_w.selection_name = ?)) "
        "GROUP BY a.type"
    )
    assert compiled.params == ("my_entity_sel",)


def test_render_always_false():
    compiled = render(CountAxiomsByType(constraints=(AlwaysFalse(),)))
    assert compiled.sql == "SELECT a.type, COUNT(*) FROM axioms a WHERE 0 GROUP BY a.type"
    assert compiled.params == ()


def test_render_always_false_short_circuits_other_constraints():
    compiled = render(
        CountAxiomsByType(
            constraints=(
                OfTypes(tags=("Declaration",)),
                AlwaysFalse(),
                MentionsAny(iris=(IRI("ex:A"),)),
            )
        )
    )
    assert compiled.sql == "SELECT a.type, COUNT(*) FROM axioms a WHERE 0 GROUP BY a.type"
    assert compiled.params == ()


def test_render_conjunction():
    # render() does not normalize: fragments emit in the input-constraint order.
    compiled = render(
        CountAxiomsByType(
            constraints=(OfTypes(tags=("Declaration",)), MentionsAny(iris=(IRI("ex:A"),)))
        )
    )
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "a.type IN (?) AND "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri IN (?)) "
        "GROUP BY a.type"
    )
    assert compiled.params == ("Declaration", "ex:A")


# -- _run integration --


def test_run_empty_ontology(s):
    assert _run(s, CountAxiomsByType(constraints=())) == Counter()


def test_run_groups_by_type(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Cat"), super_class=IRI("ex:Animal")),
        ],
    )

    result = _run(s, CountAxiomsByType(constraints=()))
    assert result == Counter({"Declaration": 3, "SubClassOf": 2})


def test_run_filter_by_of_types(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
        ],
    )
    result = _run(s, CountAxiomsByType(constraints=(OfTypes(tags=("SubClassOf",)),)))
    assert result == Counter({"SubClassOf": 1})


def test_run_mentions_all_requires_all_iris_present(s):
    # Two SubClassOf axioms; only one mentions both Dog and Animal.
    add_axioms(
        s,
        [
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Cat"), super_class=IRI("ex:Mammal")),
        ],
    )
    result = _run(
        s,
        CountAxiomsByType(constraints=(MentionsAll(iris=(IRI("ex:Dog"), IRI("ex:Animal"))),)),
    )
    assert result == Counter({"SubClassOf": 1})


def test_run_mentions_any_any_of_iris(s):
    add_axioms(
        s,
        [
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Cat"), super_class=IRI("ex:Mammal")),
            SubClassOf(sub_class=IRI("ex:Fish"), super_class=IRI("ex:Vertebrate")),
        ],
    )
    result = _run(
        s,
        CountAxiomsByType(constraints=(MentionsAny(iris=(IRI("ex:Dog"), IRI("ex:Cat"))),)),
    )
    assert result == Counter({"SubClassOf": 2})


def test_run_count_star_no_row_multiplicity_with_mentions_any(s):
    # An axiom mentioning BOTH iris in a MentionsAny list must still count once.
    add_axioms(s, [SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))])
    result = _run(
        s,
        CountAxiomsByType(constraints=(MentionsAny(iris=(IRI("ex:Dog"), IRI("ex:Animal"))),)),
    )
    assert result == Counter({"SubClassOf": 1})


def test_run_in_selection_axioms(s):
    dog_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    cat_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat"))
    sub = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))

    add_axioms(s, [dog_decl, cat_decl, sub])

    upsert_selection(
        s,
        SelectionName("axiom_pair"),
        SelectionKind.AXIOMS,
        [HashedAxiom.of(dog_decl).hash, HashedAxiom.of(sub).hash],
        source="test",
    )
    ref = ResolvedSelection(kind=SelectionKind.AXIOMS, bare_name="axiom_pair")
    result = _run(s, CountAxiomsByType(constraints=(InSelection(ref=ref),)))
    assert result == Counter({"Declaration": 1, "SubClassOf": 1})


def test_run_in_selection_entities(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
        ],
    )
    upsert_selection(
        s,
        SelectionName("dog_only"),
        SelectionKind.ENTITIES,
        ["ex:Dog"],
        source="test",
    )
    ref = ResolvedSelection(kind=SelectionKind.ENTITIES, bare_name="dog_only")
    result = _run(s, CountAxiomsByType(constraints=(InSelection(ref=ref),)))
    # Dog declaration mentions ex:Dog; SubClassOf mentions ex:Dog.
    # Cat declaration does not mention ex:Dog.
    assert result == Counter({"Declaration": 1, "SubClassOf": 1})


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert _run(s, CountAxiomsByType(constraints=(AlwaysFalse(),))) == Counter()


def test_run_returns_str_keys(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = _run(s, CountAxiomsByType(constraints=()))
    assert len(result) == 1
    key = next(iter(result))
    assert isinstance(key, str)
    assert key == "Declaration"
