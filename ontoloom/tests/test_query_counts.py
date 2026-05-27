"""Tests for CountEntities, CountEntitiesByRole, and CountAxiomsByType.

The three queries share a constraint vocabulary; this file keeps tests
grouped by query, with cross-query shape checks parametrized at the bottom
of each section.
"""

from collections import Counter

import pytest
from ontoloom.axioms.mutations import add_axioms
from ontoloom.axioms.types import HashedAxiom
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import AxiomTag, Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes.types import PrefixName
from ontoloom.query.constraints import (
    AlwaysFalse,
    HasRole,
    InAxiomSelection,
    InEntitySelection,
    InIRIs,
    InNamespaces,
    MentionsAll,
    MentionsAny,
    WithRoles,
    WithTypes,
)
from ontoloom.query.count_axioms_by_type import CountAxiomsByType
from ontoloom.query.count_entities import CountEntities
from ontoloom.query.count_entities_by_role import CountEntitiesByRole
from ontoloom.query.dispatch import run
from ontoloom.selections.store import upsert_axiom_selection, upsert_entity_selection
from ontoloom.selections.types import SelectionName

# =============================================================================
# CountEntities
# =============================================================================


def test_ce_run_single_declaration(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert run(s, CountEntities(constraints=())) == 1


def test_ce_run_multiple_role_filter(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI("ex:hasOwner")),
        ],
    )
    assert run(s, CountEntities(constraints=(HasRole(),))) == 3
    assert run(s, CountEntities(constraints=(WithRoles(roles=(EntityType.CLASS,)),))) == 2
    assert run(s, CountEntities(constraints=(WithRoles(roles=(EntityType.OBJECT_PROPERTY,)),))) == 1


def test_ce_run_in_selection_entities(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
        ],
    )
    upsert_entity_selection(
        s,
        SelectionName("dogs_and_cats"),
        ["ex:Dog", "ex:Cat"],
        source="test",
    )
    ref = SelectionName("dogs_and_cats")
    assert run(s, CountEntities(constraints=(InEntitySelection(name=ref),))) == 2


def test_ce_run_in_selection_axioms(s):
    dog_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    cat_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat"))
    add_axioms(s, [dog_decl, cat_decl])
    upsert_axiom_selection(
        s,
        SelectionName("dog_only"),
        [HashedAxiom.of(dog_decl).hash],
        source="test",
    )
    ref = SelectionName("dog_only")
    assert run(s, CountEntities(constraints=(InAxiomSelection(name=ref),))) == 1


def test_ce_run_namespace_filter(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("other:Fish")),
        ],
    )
    assert run(s, CountEntities(constraints=(InNamespaces(namespaces=(PrefixName("ex"),)),))) == 1
    assert (
        run(
            s,
            CountEntities(
                constraints=(InNamespaces(namespaces=(PrefixName("ex"), PrefixName("other"))),)
            ),
        )
        == 2
    )


def test_ce_run_normalize_runs_before_render(s):
    # normalize_entity intersects two InIRIs into one; the result is a
    # single-element set, and the SQL run should still match.
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    q = CountEntities(
        constraints=(
            InIRIs(iris=(IRI("ex:Dog"), IRI("ex:Cat"))),
            InIRIs(iris=(IRI("ex:Dog"), IRI("ex:Fish"))),
        )
    )
    assert run(s, q) == 1


# =============================================================================
# CountEntitiesByRole
# =============================================================================


def test_cebr_run_groups_by_role(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI("ex:hasOwner")),
            Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI("ex:hasParent")),
            Declaration(entity_type=EntityType.DATA_PROPERTY, iri=IRI("ex:age")),
            Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI("ex:rex")),
        ],
    )
    result = run(s, CountEntitiesByRole(constraints=()))
    assert result == Counter(
        {
            EntityType.CLASS: 3,
            EntityType.OBJECT_PROPERTY: 2,
            EntityType.DATA_PROPERTY: 1,
            EntityType.NAMED_INDIVIDUAL: 1,
        }
    )


def test_cebr_run_returns_entity_type_keys(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = run(s, CountEntitiesByRole(constraints=()))
    assert len(result) == 1
    key = next(iter(result))
    assert isinstance(key, EntityType)
    assert key is EntityType.CLASS


def test_cebr_run_excludes_iris_appearing_only_in_non_role_positions(s):
    # `ex:Dog` is declared as a CLASS (role=CLASS) and ALSO appears as the
    # value of an rdfs:seeAlso annotation on the Cat declaration (role=None,
    # position=VALUE). The query must count Dog exactly once (under CLASS),
    # and `ex:OnlyAsAnnotationValue` — which appears ONLY as an annotation
    # value, never with a role — must not show up at all.
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(
                entity_type=EntityType.CLASS,
                iri=IRI("ex:Cat"),
                annotations=(
                    Annotation(property=IRI("rdfs:seeAlso"), value=IRI("ex:Dog")),
                    Annotation(
                        property=IRI("rdfs:seeAlso"),
                        value=IRI("ex:OnlyAsAnnotationValue"),
                    ),
                ),
            ),
        ],
    )
    result = run(s, CountEntitiesByRole(constraints=()))
    # 2 classes (Dog, Cat). `ex:OnlyAsAnnotationValue` has no role so does
    # not appear under any key. `rdfs:seeAlso` carries role=ANNOTATION_PROPERTY.
    assert result[EntityType.CLASS] == 2
    assert result[EntityType.ANNOTATION_PROPERTY] == 1
    assert all(v > 0 for v in result.values())
    assert sum(result.values()) == 3  # Dog, Cat, rdfs:seeAlso


def test_cebr_run_filtered_by_namespace(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("other:Fish")),
            Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI("ex:hasOwner")),
        ],
    )
    result = run(
        s,
        CountEntitiesByRole(constraints=(InNamespaces(namespaces=(PrefixName("ex"),)),)),
    )
    assert result == Counter({EntityType.CLASS: 1, EntityType.OBJECT_PROPERTY: 1})


# =============================================================================
# CountAxiomsByType
# =============================================================================


def test_cabt_run_groups_by_type(s):
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
    result = run(s, CountAxiomsByType(constraints=()))
    assert result == Counter({AxiomTag.DECLARATION: 3, AxiomTag.SUB_CLASS_OF: 2})


def test_cabt_run_filter_by_of_types(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
        ],
    )
    result = run(s, CountAxiomsByType(constraints=(WithTypes(tags=(AxiomTag.SUB_CLASS_OF,)),)))
    assert result == Counter({AxiomTag.SUB_CLASS_OF: 1})


def test_cabt_run_mentions_all_requires_all_iris_present(s):
    # Two SubClassOf axioms; only one mentions both Dog and Animal.
    add_axioms(
        s,
        [
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Cat"), super_class=IRI("ex:Mammal")),
        ],
    )
    result = run(
        s,
        CountAxiomsByType(constraints=(MentionsAll(iris=(IRI("ex:Dog"), IRI("ex:Animal"))),)),
    )
    assert result == Counter({AxiomTag.SUB_CLASS_OF: 1})


def test_cabt_run_mentions_any_any_of_iris(s):
    add_axioms(
        s,
        [
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Cat"), super_class=IRI("ex:Mammal")),
            SubClassOf(sub_class=IRI("ex:Fish"), super_class=IRI("ex:Vertebrate")),
        ],
    )
    result = run(
        s,
        CountAxiomsByType(constraints=(MentionsAny(iris=(IRI("ex:Dog"), IRI("ex:Cat"))),)),
    )
    assert result == Counter({AxiomTag.SUB_CLASS_OF: 2})


def test_cabt_run_count_star_no_row_multiplicity_with_mentions_any(s):
    # An axiom mentioning BOTH iris in a MentionsAny list must still count once.
    add_axioms(s, [SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))])
    result = run(
        s,
        CountAxiomsByType(constraints=(MentionsAny(iris=(IRI("ex:Dog"), IRI("ex:Animal"))),)),
    )
    assert result == Counter({AxiomTag.SUB_CLASS_OF: 1})


def test_cabt_run_in_selection_axioms(s):
    dog_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    cat_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat"))
    sub = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    add_axioms(s, [dog_decl, cat_decl, sub])
    upsert_axiom_selection(
        s,
        SelectionName("axiom_pair"),
        [HashedAxiom.of(dog_decl).hash, HashedAxiom.of(sub).hash],
        source="test",
    )
    ref = SelectionName("axiom_pair")
    result = run(s, CountAxiomsByType(constraints=(InAxiomSelection(name=ref),)))
    assert result == Counter({AxiomTag.DECLARATION: 1, AxiomTag.SUB_CLASS_OF: 1})


def test_cabt_run_in_selection_entities(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
        ],
    )
    upsert_entity_selection(
        s,
        SelectionName("dog_only"),
        ["ex:Dog"],
        source="test",
    )
    ref = SelectionName("dog_only")
    result = run(s, CountAxiomsByType(constraints=(InEntitySelection(name=ref),)))
    # Dog declaration mentions ex:Dog; SubClassOf mentions ex:Dog.
    # Cat declaration does not mention ex:Dog.
    assert result == Counter({AxiomTag.DECLARATION: 1, AxiomTag.SUB_CLASS_OF: 1})


def test_cabt_run_returns_axiom_tag_keys(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = run(s, CountAxiomsByType(constraints=()))
    assert len(result) == 1
    key = next(iter(result))
    assert isinstance(key, AxiomTag)
    assert key is AxiomTag.DECLARATION


# =============================================================================
# Cross-query shape: empty ontology and AlwaysFalse short-circuit
#
# Parametrized because the three queries differ only in their empty-result
# value (0 vs Counter()) — the behaviour is identical.
# =============================================================================


@pytest.mark.parametrize(
    ("query", "empty"),
    [
        (CountEntities(constraints=()), 0),
        (CountEntitiesByRole(constraints=()), Counter()),
        (CountAxiomsByType(constraints=()), Counter()),
    ],
    ids=["CountEntities", "CountEntitiesByRole", "CountAxiomsByType"],
)
def test_run_empty_ontology(s, query, empty):
    assert run(s, query) == empty


@pytest.mark.parametrize(
    ("query", "empty"),
    [
        (CountEntities(constraints=(AlwaysFalse(),)), 0),
        (CountEntitiesByRole(constraints=(AlwaysFalse(),)), Counter()),
        (CountAxiomsByType(constraints=(AlwaysFalse(),)), Counter()),
    ],
    ids=["CountEntities", "CountEntitiesByRole", "CountAxiomsByType"],
)
def test_run_always_false_returns_empty(s, query, empty):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert run(s, query) == empty
