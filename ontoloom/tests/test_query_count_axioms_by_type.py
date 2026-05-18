"""Tests for the CountAxiomsByType query and the shared `_axiom_predicates` helper."""

from collections import Counter

from ontoloom.axioms.store import add_axioms
from ontoloom.hashing import HashedAxiom
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import AxiomTag, EntityType
from ontoloom.query.constraints import (
    AlwaysFalse,
    InSelection,
    MentionsAll,
    MentionsAny,
    WithTypes,
)
from ontoloom.query.count_axioms_by_type import CountAxiomsByType
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import (
    AxiomSelectionName,
    EntitySelectionName,
    SelectionKind,
    SelectionName,
)

# -- render snapshots: no DB --


def test_render_no_constraints():
    compiled = (CountAxiomsByType(constraints=())).render()
    assert compiled.sql == "SELECT a.type, COUNT(*) FROM axioms a WHERE 1 GROUP BY a.type"
    assert compiled.params == ()


def test_render_of_types_single():
    compiled = (CountAxiomsByType(constraints=(WithTypes(tags=(AxiomTag.DECLARATION,)),))).render()
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE a.type IN (?) GROUP BY a.type"
    )
    assert compiled.params == ("Declaration",)


def test_render_of_types_many():
    compiled = (
        CountAxiomsByType(
            constraints=(WithTypes(tags=(AxiomTag.SUB_CLASS_OF, AxiomTag.DECLARATION)),)
        )
    ).render()
    # tags are deduped and sorted by the field validator.
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE a.type IN (?,?) GROUP BY a.type"
    )
    assert compiled.params == ("Declaration", "SubClassOf")


def test_render_mentions_all_single():
    compiled = (CountAxiomsByType(constraints=(MentionsAll(iris=(IRI("ex:A"),)),))).render()
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri = ?) "
        "GROUP BY a.type"
    )
    assert compiled.params == ("ex:A",)


def test_render_mentions_all_multi_emits_one_exists_per_iri():
    compiled = (
        CountAxiomsByType(constraints=(MentionsAll(iris=(IRI("ex:B"), IRI("ex:A"))),))
    ).render()
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
    compiled = (CountAxiomsByType(constraints=(MentionsAny(iris=(IRI("ex:A"),)),))).render()
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri IN (?)) "
        "GROUP BY a.type"
    )
    assert compiled.params == ("ex:A",)


def test_render_mentions_any_many():
    compiled = (
        CountAxiomsByType(constraints=(MentionsAny(iris=(IRI("ex:B"), IRI("ex:A"))),))
    ).render()
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri IN (?,?)) "
        "GROUP BY a.type"
    )
    assert compiled.params == ("ex:A", "ex:B")


def test_render_in_selection_axioms():
    ref = AxiomSelectionName("axioms:my_axiom_sel")
    compiled = (CountAxiomsByType(constraints=(InSelection(ref=ref),))).render()
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM selection_items si_w "
        "WHERE si_w.item = a.hash AND si_w.selection_name = ?) "
        "GROUP BY a.type"
    )
    assert compiled.params == ("my_axiom_sel",)


def test_render_in_selection_entities():
    ref = EntitySelectionName("entities:my_entity_sel")
    compiled = (CountAxiomsByType(constraints=(InSelection(ref=ref),))).render()
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM selection_items si_w "
        "JOIN axiom_entities ae_w ON ae_w.entity_iri = si_w.item "
        "WHERE si_w.selection_name = ? AND ae_w.axiom_id = a.id) "
        "GROUP BY a.type"
    )
    assert compiled.params == ("my_entity_sel",)


def test_render_always_false():
    compiled = (CountAxiomsByType(constraints=(AlwaysFalse(),))).render()
    assert compiled.sql == "SELECT a.type, COUNT(*) FROM axioms a WHERE 0 GROUP BY a.type"
    assert compiled.params == ()


def test_render_always_false_short_circuits_other_constraints():
    compiled = (
        CountAxiomsByType(
            constraints=(
                WithTypes(tags=(AxiomTag.DECLARATION,)),
                AlwaysFalse(),
                MentionsAny(iris=(IRI("ex:A"),)),
            )
        )
    ).render()
    assert compiled.sql == "SELECT a.type, COUNT(*) FROM axioms a WHERE 0 GROUP BY a.type"
    assert compiled.params == ()


def test_render_conjunction():
    # ().render() normalizes (sorts constraints by repr) before emitting fragments.
    compiled = (
        CountAxiomsByType(
            constraints=(WithTypes(tags=(AxiomTag.DECLARATION,)), MentionsAny(iris=(IRI("ex:A"),)))
        )
    ).render()
    assert compiled.sql == (
        "SELECT a.type, COUNT(*) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri IN (?)) "
        "AND a.type IN (?) "
        "GROUP BY a.type"
    )
    assert compiled.params == ("ex:A", "Declaration")


# -- _run integration --


def test_run_empty_ontology(s):
    assert (CountAxiomsByType(constraints=()))._run(s) == Counter()


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

    result = (CountAxiomsByType(constraints=()))._run(s)
    assert result == Counter({AxiomTag.DECLARATION: 3, AxiomTag.SUB_CLASS_OF: 2})


def test_run_filter_by_of_types(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
        ],
    )
    result = (CountAxiomsByType(constraints=(WithTypes(tags=(AxiomTag.SUB_CLASS_OF,)),)))._run(s)
    assert result == Counter({AxiomTag.SUB_CLASS_OF: 1})


def test_run_mentions_all_requires_all_iris_present(s):
    # Two SubClassOf axioms; only one mentions both Dog and Animal.
    add_axioms(
        s,
        [
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Cat"), super_class=IRI("ex:Mammal")),
        ],
    )
    result = CountAxiomsByType(
        constraints=(MentionsAll(iris=(IRI("ex:Dog"), IRI("ex:Animal"))),)
    )._run(s)
    assert result == Counter({AxiomTag.SUB_CLASS_OF: 1})


def test_run_mentions_any_any_of_iris(s):
    add_axioms(
        s,
        [
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Cat"), super_class=IRI("ex:Mammal")),
            SubClassOf(sub_class=IRI("ex:Fish"), super_class=IRI("ex:Vertebrate")),
        ],
    )
    result = CountAxiomsByType(
        constraints=(MentionsAny(iris=(IRI("ex:Dog"), IRI("ex:Cat"))),)
    )._run(s)
    assert result == Counter({AxiomTag.SUB_CLASS_OF: 2})


def test_run_count_star_no_row_multiplicity_with_mentions_any(s):
    # An axiom mentioning BOTH iris in a MentionsAny list must still count once.
    add_axioms(s, [SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))])
    result = CountAxiomsByType(
        constraints=(MentionsAny(iris=(IRI("ex:Dog"), IRI("ex:Animal"))),)
    )._run(s)
    assert result == Counter({AxiomTag.SUB_CLASS_OF: 1})


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
    ref = AxiomSelectionName("axioms:axiom_pair")
    result = (CountAxiomsByType(constraints=(InSelection(ref=ref),)))._run(s)
    assert result == Counter({AxiomTag.DECLARATION: 1, AxiomTag.SUB_CLASS_OF: 1})


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
    ref = EntitySelectionName("entities:dog_only")
    result = (CountAxiomsByType(constraints=(InSelection(ref=ref),)))._run(s)
    # Dog declaration mentions ex:Dog; SubClassOf mentions ex:Dog.
    # Cat declaration does not mention ex:Dog.
    assert result == Counter({AxiomTag.DECLARATION: 1, AxiomTag.SUB_CLASS_OF: 1})


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert (CountAxiomsByType(constraints=(AlwaysFalse(),)))._run(s) == Counter()


def test_run_returns_axiom_tag_keys(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = (CountAxiomsByType(constraints=()))._run(s)
    assert len(result) == 1
    key = next(iter(result))
    assert isinstance(key, AxiomTag)
    assert key is AxiomTag.DECLARATION
