import pytest
from ontoloom.ontology import axioms, selections
from ontoloom.ontology.canonical import axiom_hash
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.axioms import (
    Declaration,
    EquivalentClasses,
    SubClassOf,
    SubObjectPropertyOfChain,
)
from ontoloom.ontology.models.expressions import NamedClass
from ontoloom.ontology.models.literals import IRI, EntityType
from ontoloom.ontology.patterns import (
    ContainsExpr,
    EquivalentClassesPattern,
    NamedClassPattern,
    SubClassOfPattern,
    SubObjectPropertyOfChainPattern,
)
from ontoloom.ontology.patterns.search import match_axioms
from ontoloom.ontology.patterns.slot import Slot
from ontoloom.ontology.selections import SelectionKind


@pytest.fixture()
def ont(tmp_path):
    path = tmp_path / "test.ontology.db"
    Ontology.create(path)
    with Ontology(path) as o:
        yield o


@pytest.fixture()
def populated(ont):
    from ontoloom.ontology.models.axioms import ObjectPropertyDomain

    axioms.add(
        ont,
        [
            SubClassOf(
                sub_class=NamedClass(iri=IRI("ex:Dog")),
                super_class=NamedClass(iri=IRI("ex:Animal")),
            ),
            SubClassOf(
                sub_class=NamedClass(iri=IRI("ex:Cat")),
                super_class=NamedClass(iri=IRI("ex:Animal")),
            ),
            ObjectPropertyDomain(property=IRI("ex:hasOwner"), domain=NamedClass(iri=IRI("ex:Pet"))),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
        ],
    )
    return ont


def test_axiom_type_filter(populated):
    pattern = SubClassOfPattern(sub_class=Slot("*"), super_class=Slot("*"))
    result = match_axioms(populated, pattern)
    assert result.total == 2
    for h in result.axiom_hashes:
        row = populated.conn.execute("SELECT type FROM axioms WHERE hash = ?", (h,)).fetchone()
        assert row is not None
        assert row[0] == "SubClassOf"


def test_expression_level_hits_container_types_not_declarations(populated):
    pattern = NamedClassPattern(iri=Slot("ex:Animal"))
    result = match_axioms(populated, pattern)
    assert result.total > 0
    for h in result.axiom_hashes:
        row = populated.conn.execute("SELECT type FROM axioms WHERE hash = ?", (h,)).fetchone()
        assert row is not None
        assert row[0] != "Declaration"


def test_within_axiom_selection(populated):
    dog_ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")), super_class=NamedClass(iri=IRI("ex:Animal"))
    )
    dog_hash = axiom_hash(dog_ax)

    selections.upsert(populated, "dog_only", SelectionKind.AXIOMS, [dog_hash], source="test")

    pattern = SubClassOfPattern(sub_class=Slot("*"), super_class=Slot("*"))
    result = match_axioms(populated, pattern, within="dog_only")
    assert result.total == 1
    assert result.axiom_hashes[0] == dog_hash


def test_within_entity_selection(populated):
    selections.upsert(populated, "cat_entities", SelectionKind.ENTITIES, ["ex:Cat"], source="test")

    pattern = SubClassOfPattern(sub_class=Slot("*"), super_class=Slot("*"))
    result = match_axioms(populated, pattern, within="cat_entities")
    assert result.total == 1

    cat_ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Cat")), super_class=NamedClass(iri=IRI("ex:Animal"))
    )
    assert result.axiom_hashes[0] == axiom_hash(cat_ax)


def test_variable_cross_position_same_value(populated):
    self_ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Self")), super_class=NamedClass(iri=IRI("ex:Self"))
    )
    axioms.add(populated, [self_ax])

    pattern = SubClassOfPattern(sub_class=Slot("?C"), super_class=Slot("?C"))
    result = match_axioms(populated, pattern)
    assert result.total == 1
    assert result.axiom_hashes[0] == axiom_hash(self_ax)


def test_index_narrowing_with_many_iris(populated):
    chain_ax = SubObjectPropertyOfChain(
        chain=(IRI("ex:r1"), IRI("ex:r2"), IRI("ex:r3"), IRI("ex:r4")),
        super_property=IRI("ex:s"),
    )
    axioms.add(populated, [chain_ax])

    pattern = SubObjectPropertyOfChainPattern(
        chain=(Slot("ex:r1"), Slot("ex:r2"), Slot("ex:r3"), Slot("ex:r4")),
        super_property=Slot("ex:s"),
    )
    result = match_axioms(populated, pattern)
    assert result.total == 1


def test_contains_partial_set_match(populated):
    ec_ax = EquivalentClasses(
        expressions=(
            NamedClass(iri=IRI("ex:A")),
            NamedClass(iri=IRI("ex:B")),
            NamedClass(iri=IRI("ex:C")),
        )
    )
    axioms.add(populated, [ec_ax])

    pattern = EquivalentClassesPattern(
        expressions=ContainsExpr(contains=(NamedClassPattern(iri=Slot("ex:A")),))
    )
    result = match_axioms(populated, pattern)
    assert result.total >= 1
    assert axiom_hash(ec_ax) in result.axiom_hashes


def test_pattern_matches_nothing(populated):
    pattern = SubClassOfPattern(sub_class=Slot("ex:Nonexistent"), super_class=Slot("*"))
    result = match_axioms(populated, pattern)
    assert result.total == 0


def test_match_limit_truncates_and_flags(populated):
    pattern = SubClassOfPattern(sub_class=Slot("*"), super_class=Slot("*"))
    full = match_axioms(populated, pattern)
    assert full.total == 2
    assert full.truncated is False

    capped = match_axioms(populated, pattern, limit=1)
    assert capped.total == 1
    assert capped.truncated is True
    assert capped.axiom_hashes[0] in full.axiom_hashes


def test_match_limit_not_hit_no_truncation(populated):
    pattern = SubClassOfPattern(sub_class=Slot("*"), super_class=Slot("*"))
    result = match_axioms(populated, pattern, limit=10)
    assert result.total == 2
    assert result.truncated is False
