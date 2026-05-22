import pytest
from ontoloom.axioms.mutations import add_axioms
from ontoloom.axioms.types import HashedAxiom
from ontoloom.owl.axioms import (
    AnnotationAssertion,
    Declaration,
    EquivalentClasses,
    SubClassOf,
    SubObjectPropertyOfChain,
)
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import BCP47Tag, LangLiteral, TypedLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.patterns.match import _match_slot_vs_expression
from ontoloom.patterns.slot import IRISlot, VariableSlot, WildcardSlot
from ontoloom.patterns.store import match_axioms
from ontoloom.patterns.types import (
    AnnotationAssertionPattern,
    EquivalentClassesPattern,
    ObjectSomeValuesFromPattern,
    SubClassOfPattern,
    SubObjectPropertyOfChainPattern,
    TupleMatch,
)
from ontoloom.selections.persistence import upsert_selection
from ontoloom.selections.types import (
    AxiomSelectionName,
    EntitySelectionName,
    SelectionKind,
    SelectionName,
)


@pytest.fixture()
def populated(s):
    from ontoloom.owl.axioms import ObjectPropertyDomain

    add_axioms(
        s,
        [
            SubClassOf(
                sub_class=IRI("ex:Dog"),
                super_class=IRI("ex:Animal"),
            ),
            SubClassOf(
                sub_class=IRI("ex:Cat"),
                super_class=IRI("ex:Animal"),
            ),
            ObjectPropertyDomain(object_property=IRI("ex:hasOwner"), domain=IRI("ex:Pet")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
        ],
    )
    return s


def test_axiom_type_filter(populated):
    pattern = SubClassOfPattern(sub_class=WildcardSlot("*"), super_class=WildcardSlot("*"))
    result = match_axioms(populated, pattern)
    assert len(result.axiom_hashes) == 2
    for h in result.axiom_hashes:
        row = populated.conn.execute("SELECT type FROM axioms WHERE hash = ?", (h,)).fetchone()
        assert row is not None
        assert row[0] == "SubClassOf"


def test_expression_level_hits_container_types_not_declarations(populated):
    from ontoloom.owl.expressions import ObjectSomeValuesFrom

    add_axioms(
        populated,
        [
            SubClassOf(
                sub_class=IRI("ex:Dog"),
                super_class=ObjectSomeValuesFrom(
                    property=IRI("ex:hasPart"), filler=IRI("ex:Heart")
                ),
            )
        ],
    )
    pattern = ObjectSomeValuesFromPattern(property=WildcardSlot("*"), filler=WildcardSlot("*"))
    result = match_axioms(populated, pattern)
    assert len(result.axiom_hashes) > 0

    for h in result.axiom_hashes:
        row = populated.conn.execute("SELECT type FROM axioms WHERE hash = ?", (h,)).fetchone()
        assert row is not None
        assert row[0] != "Declaration"


def test_within_axiom_selection(populated):
    dog_ax = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    dog_hash = HashedAxiom.of(dog_ax).hash

    upsert_selection(
        populated, SelectionName("dog_only"), SelectionKind.AXIOMS, [dog_hash], source="test"
    )

    pattern = SubClassOfPattern(sub_class=WildcardSlot("*"), super_class=WildcardSlot("*"))
    result = match_axioms(
        populated,
        pattern,
        within=AxiomSelectionName("axioms:dog_only"),
    )
    assert len(result.axiom_hashes) == 1
    assert result.axiom_hashes[0] == dog_hash


def test_within_entity_selection(populated):
    upsert_selection(
        populated,
        SelectionName("cat_entities"),
        SelectionKind.ENTITIES,
        ["ex:Cat"],
        source="test",
    )

    pattern = SubClassOfPattern(sub_class=WildcardSlot("*"), super_class=WildcardSlot("*"))
    result = match_axioms(
        populated,
        pattern,
        within=EntitySelectionName("entities:cat_entities"),
    )
    assert len(result.axiom_hashes) == 1

    cat_ax = SubClassOf(sub_class=IRI("ex:Cat"), super_class=IRI("ex:Animal"))
    assert result.axiom_hashes[0] == HashedAxiom.of(cat_ax).hash


def test_variable_cross_position_same_value(populated):
    self_ax = SubClassOf(sub_class=IRI("ex:Self"), super_class=IRI("ex:Self"))
    add_axioms(populated, [self_ax])

    pattern = SubClassOfPattern(sub_class=VariableSlot("?C"), super_class=VariableSlot("?C"))
    result = match_axioms(populated, pattern)
    assert len(result.axiom_hashes) == 1
    assert result.axiom_hashes[0] == HashedAxiom.of(self_ax).hash


def test_index_narrowing_with_many_iris(populated):
    chain_ax = SubObjectPropertyOfChain(
        chain=(IRI("ex:r1"), IRI("ex:r2"), IRI("ex:r3"), IRI("ex:r4")),
        super_property=IRI("ex:s"),
    )
    add_axioms(populated, [chain_ax])

    pattern = SubObjectPropertyOfChainPattern(
        chain=(IRISlot("ex:r1"), IRISlot("ex:r2"), IRISlot("ex:r3"), IRISlot("ex:r4")),
        super_property=IRISlot("ex:s"),
    )
    result = match_axioms(populated, pattern)
    assert len(result.axiom_hashes) == 1


def test_contains_partial_set_match(populated):
    ec_ax = EquivalentClasses(
        equivalent_classes=(
            IRI("ex:A"),
            IRI("ex:B"),
            IRI("ex:C"),
        )
    )
    add_axioms(populated, [ec_ax])

    pattern = EquivalentClassesPattern(
        equivalent_classes=(IRISlot("ex:A"),),
        equivalent_classes_match=TupleMatch.PARTIAL,
    )
    result = match_axioms(populated, pattern)
    assert len(result.axiom_hashes) >= 1
    assert HashedAxiom.of(ec_ax).hash in result.axiom_hashes


def test_pattern_matches_nothing(populated):
    pattern = SubClassOfPattern(sub_class=IRISlot("ex:Nonexistent"), super_class=WildcardSlot("*"))
    result = match_axioms(populated, pattern)
    assert len(result.axiom_hashes) == 0


def test_match_limit_truncates_and_flags(populated):
    pattern = SubClassOfPattern(sub_class=WildcardSlot("*"), super_class=WildcardSlot("*"))
    full = match_axioms(populated, pattern)
    assert len(full.axiom_hashes) == 2
    assert full.truncated is False

    capped = match_axioms(populated, pattern, limit=1)
    assert len(capped.axiom_hashes) == 1
    assert capped.truncated is True
    assert capped.axiom_hashes[0] in full.axiom_hashes


def test_match_limit_not_hit_no_truncation(populated):
    pattern = SubClassOfPattern(sub_class=WildcardSlot("*"), super_class=WildcardSlot("*"))
    result = match_axioms(populated, pattern, limit=10)
    assert len(result.axiom_hashes) == 2
    assert result.truncated is False


def test_match_slot_vs_expression_concrete_slot_matches_bare_iri():
    slot = IRISlot("ex:Dog")
    bindings = _match_slot_vs_expression(slot, IRI("ex:Dog"), {})
    assert bindings == {}


def test_match_slot_vs_expression_concrete_slot_rejects_mismatched_bare_iri():
    slot = IRISlot("ex:Dog")
    assert _match_slot_vs_expression(slot, IRI("ex:Cat"), {}) is None


def test_match_slot_vs_expression_variable_binds_bare_iri():
    slot = VariableSlot("?C")
    bindings = _match_slot_vs_expression(slot, IRI("ex:Dog"), {})
    assert bindings == {"C": "ex:Dog"}


def test_match_slot_vs_expression_variable_binds_iri_object():
    slot = VariableSlot("?C")
    bindings = _match_slot_vs_expression(slot, IRI("ex:Dog"), {})
    assert bindings == {"C": "ex:Dog"}


@pytest.fixture()
def labeled(s):
    add_axioms(
        s,
        [
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Dog"),
                value=LangLiteral(value="Dog", lang=BCP47Tag("en")),
            ),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Cat"),
                value=LangLiteral(value="Cat", lang=BCP47Tag("en")),
            ),
            AnnotationAssertion(
                property=IRI("rdfs:comment"),
                subject=IRI("ex:Dog"),
                value=TypedLiteral(value="A canine."),
            ),
        ],
    )
    return s


def test_slot_variable_matches_lang_literal_value(labeled):
    pattern = AnnotationAssertionPattern(
        property=IRISlot("rdfs:label"),
        subject=VariableSlot("?s"),
        value=VariableSlot("?v"),
    )
    result = match_axioms(labeled, pattern)
    assert len(result.axiom_hashes) == 2


def test_slot_wildcard_matches_typed_literal_value(labeled):
    pattern = AnnotationAssertionPattern(
        property=IRISlot("rdfs:comment"),
        subject=WildcardSlot("*"),
        value=WildcardSlot("*"),
    )
    result = match_axioms(labeled, pattern)
    assert len(result.axiom_hashes) == 1


def test_slot_variable_against_literal_does_not_unify_with_iri_in_other_position(labeled):
    # Same variable in subject (binds to "ex:Dog") and value (binds to '"Dog"@en')
    # must NOT unify — different canonical strings, no match.
    pattern = AnnotationAssertionPattern(
        property=IRISlot("rdfs:label"),
        subject=VariableSlot("?x"),
        value=VariableSlot("?x"),
    )
    result = match_axioms(labeled, pattern)
    assert len(result.axiom_hashes) == 0
