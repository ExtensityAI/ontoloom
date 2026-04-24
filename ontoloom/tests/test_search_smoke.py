"""Exhaustive smoke test for search_entities and search_axioms.

Builds a realistic ontology with diverse axiom types, then verifies that
every entity and axiom is discoverable through all applicable search paths.
"""

import tempfile
from pathlib import Path

import pytest
from ontoloom.ontology import axioms, entities
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.assertions import (
    ClassAssertion,
    DataPropertyAssertion,
    DifferentIndividuals,
    NegativeDataPropertyAssertion,
    NegativeObjectPropertyAssertion,
    ObjectPropertyAssertion,
    SameIndividual,
)
from ontoloom.ontology.models.axioms import (
    AnnotationAssertion,
    AnnotationPropertyDomain,
    AnnotationPropertyRange,
    DataPropertyDomain,
    DataPropertyRange,
    DatatypeDefinition,
    Declaration,
    DisjointClasses,
    EquivalentClasses,
    EquivalentDataProperties,
    EquivalentObjectProperties,
    FunctionalDataProperty,
    HasKey,
    ObjectPropertyDomain,
    ObjectPropertyRange,
    ReflexiveObjectProperty,
    SubAnnotationPropertyOf,
    SubClassOf,
    SubDataPropertyOf,
    SubObjectPropertyOf,
    SubObjectPropertyOfChain,
    TransitiveObjectProperty,
)
from ontoloom.ontology.models.base import EntityType
from ontoloom.ontology.models.expressions import (
    DataHasValue,
    DataSomeValuesFrom,
    NamedClass,
    ObjectHasSelf,
    ObjectHasValue,
    ObjectIntersectionOf,
    ObjectOneOf,
    ObjectSomeValuesFrom,
)
from ontoloom.ontology.models.literals import (
    IRI,
    Annotation,
    DataOneOf,
    DataType,
    LangLiteral,
    TypedLiteral,
)


@pytest.fixture
def ont():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.db"
        Ontology.create(path)
        with Ontology(path) as o:
            yield o


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def nc(iri: str) -> NamedClass:
    return NamedClass(iri=IRI(iri))


def _all_entity_iris(ont: Ontology) -> set[str]:
    """Collect all entity IRIs via list-all search."""
    iris = set()
    page = entities.search(ont, limit=1000)
    for m in page.matches:
        iris.add(str(m.iri))
    return iris


def _search_entities_text(ont: Ontology, query: str) -> set[str]:
    page = entities.search(ont, query=query, limit=1000)
    return {str(m.iri) for m in page.matches}


def _search_entities_role(ont: Ontology, role: str) -> set[str]:
    page = entities.search(ont, role=role, limit=1000)
    return {str(m.iri) for m in page.matches}


def _search_entities_ns(ont: Ontology, namespace: str) -> set[str]:
    page = entities.search(ont, namespace=namespace, limit=1000)
    return {str(m.iri) for m in page.matches}


def _search_axioms_iri(ont: Ontology, iri: str) -> list:
    return axioms.search(ont, iri=IRI(iri), limit=1000).axioms


def _search_axioms_type(ont: Ontology, axiom_type: str) -> list:
    return axioms.search(ont, axiom_types=[axiom_type], limit=1000).axioms


def _search_axioms_ann(ont: Ontology, query: str) -> list:
    return axioms.search(ont, annotation_query=query, limit=1000).axioms


# ---------------------------------------------------------------------------
# The big ontology
# ---------------------------------------------------------------------------

AXIOMS = [
    # --- Declarations ---
    Declaration(entity_type=EntityType.CLASS, iri=IRI(":Animal")),
    Declaration(entity_type=EntityType.CLASS, iri=IRI(":Dog")),
    Declaration(entity_type=EntityType.CLASS, iri=IRI(":Cat")),
    Declaration(entity_type=EntityType.CLASS, iri=IRI(":Mammal")),
    Declaration(entity_type=EntityType.CLASS, iri=IRI(":Pet")),
    Declaration(entity_type=EntityType.CLASS, iri=IRI(":Person")),
    Declaration(entity_type=EntityType.CLASS, iri=IRI(":Mother")),
    Declaration(entity_type=EntityType.CLASS, iri=IRI(":Woman")),
    Declaration(entity_type=EntityType.CLASS, iri=IRI(":Parent")),
    Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI(":owns")),
    Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI(":hasPart")),
    Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI(":hasParent")),
    Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI(":hasMother")),
    Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI(":hasBrother")),
    Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI(":hasUncle")),
    Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI(":likes")),
    Declaration(entity_type=EntityType.DATA_PROPERTY, iri=IRI(":hasAge")),
    Declaration(entity_type=EntityType.DATA_PROPERTY, iri=IRI(":hasName")),
    Declaration(entity_type=EntityType.DATA_PROPERTY, iri=IRI(":hasWeight")),
    Declaration(entity_type=EntityType.ANNOTATION_PROPERTY, iri=IRI("rdfs:label")),
    Declaration(entity_type=EntityType.ANNOTATION_PROPERTY, iri=IRI("rdfs:comment")),
    Declaration(entity_type=EntityType.ANNOTATION_PROPERTY, iri=IRI("skos:definition")),
    Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI(":Alice")),
    Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI(":Bob")),
    Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI(":Fido")),
    Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI(":Rex")),
    Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI(":Whiskers")),
    Declaration(entity_type=EntityType.DATATYPE, iri=IRI("ex:PositiveAge")),
    # --- AnnotationAssertions (entity labels/descriptions) ---
    AnnotationAssertion(
        property=IRI("rdfs:label"),
        subject=IRI(":Dog"),
        value=LangLiteral(value="Dog", lang="en"),
    ),
    AnnotationAssertion(
        property=IRI("rdfs:label"),
        subject=IRI(":Dog"),
        value=LangLiteral(value="Hund", lang="de"),
    ),
    AnnotationAssertion(
        property=IRI("rdfs:label"),
        subject=IRI(":Cat"),
        value=LangLiteral(value="Cat", lang="en"),
    ),
    AnnotationAssertion(
        property=IRI("rdfs:comment"),
        subject=IRI(":Animal"),
        value=LangLiteral(value="A living creature that can move"),
    ),
    AnnotationAssertion(
        property=IRI("skos:definition"),
        subject=IRI(":Pet"),
        value=LangLiteral(value="A domesticated animal kept for companionship"),
    ),
    AnnotationAssertion(
        property=IRI("rdfs:label"),
        subject=IRI(":Alice"),
        value=LangLiteral(value="Alice Smith"),
    ),
    # --- SubClassOf ---
    SubClassOf(sub_class=nc(":Dog"), super_class=nc(":Animal")),
    SubClassOf(sub_class=nc(":Cat"), super_class=nc(":Animal")),
    SubClassOf(sub_class=nc(":Dog"), super_class=nc(":Pet")),
    SubClassOf(
        sub_class=nc(":Mammal"),
        super_class=ObjectSomeValuesFrom(property=IRI(":hasPart"), filler=nc(":Heart")),
    ),
    SubClassOf(
        sub_class=nc(":Person"),
        super_class=DataSomeValuesFrom(property=IRI(":hasAge"), range=DataType.INTEGER),
    ),
    SubClassOf(
        sub_class=nc(":Person"),
        super_class=ObjectIntersectionOf(operands=(nc(":Animal"), nc(":Rational"))),
    ),
    # --- EquivalentClasses ---
    EquivalentClasses(
        expressions=(
            nc(":Mother"),
            ObjectIntersectionOf(operands=(nc(":Woman"), nc(":Parent"))),
        ),
    ),
    # --- DisjointClasses ---
    DisjointClasses(expressions=(nc(":Dog"), nc(":Cat"))),
    # --- Object property axioms ---
    SubObjectPropertyOf(sub_property=IRI(":hasMother"), super_property=IRI(":hasParent")),
    SubObjectPropertyOfChain(
        chain=(IRI(":hasParent"), IRI(":hasBrother")),
        super_property=IRI(":hasUncle"),
    ),
    EquivalentObjectProperties(properties=(IRI(":owns"), IRI(":hasPet"))),
    TransitiveObjectProperty(property=IRI(":hasPart")),
    ReflexiveObjectProperty(property=IRI(":hasPart")),
    ObjectPropertyDomain(property=IRI(":owns"), domain=nc(":Person")),
    ObjectPropertyRange(property=IRI(":owns"), range=nc(":Animal")),
    # --- Data property axioms ---
    SubDataPropertyOf(sub_property=IRI(":hasWeight"), super_property=IRI(":hasMeasurement")),
    EquivalentDataProperties(properties=(IRI(":hasName"), IRI(":fullName"))),
    DataPropertyDomain(property=IRI(":hasAge"), domain=nc(":Person")),
    DataPropertyRange(property=IRI(":hasAge"), range=DataType.NON_NEGATIVE_INTEGER),
    FunctionalDataProperty(property=IRI(":hasAge")),
    # --- HasKey ---
    HasKey(
        class_expression=nc(":Person"),
        object_properties=(),
        data_properties=(IRI(":hasSSN"),),
    ),
    # --- Annotation property axioms ---
    SubAnnotationPropertyOf(
        sub_property=IRI("skos:definition"),
        super_property=IRI("rdfs:comment"),
    ),
    AnnotationPropertyDomain(property=IRI("rdfs:label"), domain=IRI("owl:Thing")),
    AnnotationPropertyRange(property=IRI("rdfs:label"), range=IRI("rdfs:Literal")),
    # --- DatatypeDefinition ---
    DatatypeDefinition(
        datatype=IRI("ex:PositiveAge"),
        data_range=DataOneOf(value=TypedLiteral(value="1", datatype=DataType.INTEGER)),
    ),
    # --- ABox assertions ---
    ClassAssertion(class_expression=nc(":Dog"), individual=IRI(":Fido")),
    ClassAssertion(class_expression=nc(":Cat"), individual=IRI(":Whiskers")),
    ClassAssertion(class_expression=nc(":Person"), individual=IRI(":Alice")),
    ObjectPropertyAssertion(property=IRI(":owns"), source=IRI(":Alice"), target=IRI(":Fido")),
    NegativeObjectPropertyAssertion(
        property=IRI(":owns"), source=IRI(":Alice"), target=IRI(":Rex")
    ),
    DataPropertyAssertion(
        property=IRI(":hasAge"),
        individual=IRI(":Alice"),
        value=TypedLiteral(value="30", datatype=DataType.INTEGER),
    ),
    NegativeDataPropertyAssertion(
        property=IRI(":hasAge"),
        individual=IRI(":Alice"),
        value=TypedLiteral(value="99", datatype=DataType.INTEGER),
    ),
    SameIndividual(individuals=(IRI(":Bob"), IRI(":Robert"))),
    DifferentIndividuals(individuals=(IRI(":Alice"), IRI(":Bob"))),
    # --- Axiom with axiom-level annotation ---
    SubClassOf(
        sub_class=nc(":Dog"),
        super_class=nc(":Mammal"),
        annotations=(
            Annotation(
                property=IRI("rdfs:comment"),
                value=LangLiteral(value="Dogs are mammals obviously"),
            ),
        ),
    ),
    # --- Expression types we want to exercise in search ---
    # ObjectOneOf
    SubClassOf(
        sub_class=nc(":Singleton"),
        super_class=ObjectOneOf(individual=IRI(":TheOne")),
    ),
    # ObjectHasValue
    SubClassOf(
        sub_class=nc(":AliceCreation"),
        super_class=ObjectHasValue(property=IRI(":hasCreator"), individual=IRI(":Alice")),
    ),
    # ObjectHasSelf
    SubClassOf(
        sub_class=nc(":Narcissist"),
        super_class=ObjectHasSelf(property=IRI(":likes")),
    ),
    # DataHasValue
    SubClassOf(
        sub_class=nc(":NamedAlice"),
        super_class=DataHasValue(property=IRI(":hasName"), value=TypedLiteral(value="Alice")),
    ),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchEntitiesComprehensive:
    """Verify every entity is findable through all applicable search paths."""

    def test_all_declared_entities_are_listed(self, ont):
        axioms.add(ont, AXIOMS)
        all_iris = _all_entity_iris(ont)
        # Every Declaration IRI must appear
        for ax in AXIOMS:
            if isinstance(ax, Declaration):
                assert str(ax.iri) in all_iris, f"Declaration {ax.iri} not in entity list"

    def test_entities_from_expressions_are_listed(self, ont):
        axioms.add(ont, AXIOMS)
        all_iris = _all_entity_iris(ont)
        # Entities mentioned only in expressions (not declared) should still appear
        # :Heart appears only in ObjectSomeValuesFrom filler
        assert ":Heart" in all_iris
        # :Rational appears only in ObjectIntersectionOf
        assert ":Rational" in all_iris
        # :TheOne appears only in ObjectOneOf
        assert ":TheOne" in all_iris
        # :hasCreator appears only in ObjectHasValue
        assert ":hasCreator" in all_iris
        # :hasPet appears only in EquivalentObjectProperties
        assert ":hasPet" in all_iris
        # :hasMeasurement appears only in SubDataPropertyOf
        assert ":hasMeasurement" in all_iris
        # :fullName appears only in EquivalentDataProperties
        assert ":fullName" in all_iris
        # :hasSSN appears only in HasKey
        assert ":hasSSN" in all_iris
        # :Robert appears only in SameIndividual
        assert ":Robert" in all_iris

    def test_search_by_local_name_exact(self, ont):
        axioms.add(ont, AXIOMS)
        results = _search_entities_text(ont, "Dog")
        assert ":Dog" in results

    def test_search_by_local_name_substring(self, ont):
        axioms.add(ont, AXIOMS)
        # "art" is substring of "hasPart"
        results = _search_entities_text(ont, "art")
        assert ":hasPart" in results

    def test_search_by_annotation_value_exact(self, ont):
        axioms.add(ont, AXIOMS)
        # "Hund" is an exact rdfs:label value for :Dog
        results = _search_entities_text(ont, "Hund")
        assert ":Dog" in results

    def test_search_by_annotation_value_substring(self, ont):
        axioms.add(ont, AXIOMS)
        # "living creature" is a substring of :Animal's rdfs:comment
        results = _search_entities_text(ont, "living creature")
        assert ":Animal" in results

    def test_search_by_annotation_value_definition(self, ont):
        axioms.add(ont, AXIOMS)
        # :Pet has a skos:definition containing "domesticated"
        results = _search_entities_text(ont, "domesticated")
        assert ":Pet" in results

    def test_search_individual_by_label(self, ont):
        axioms.add(ont, AXIOMS)
        results = _search_entities_text(ont, "Alice Smith")
        assert ":Alice" in results

    def test_search_by_role_class(self, ont):
        axioms.add(ont, AXIOMS)
        results = _search_entities_role(ont, EntityType.CLASS)
        assert ":Dog" in results
        assert ":Cat" in results
        assert ":Animal" in results
        assert ":Person" in results
        # Individuals should NOT appear
        assert ":Alice" not in results
        assert ":Fido" not in results

    def test_search_by_role_object_property(self, ont):
        axioms.add(ont, AXIOMS)
        results = _search_entities_role(ont, EntityType.OBJECT_PROPERTY)
        assert ":owns" in results
        assert ":hasPart" in results
        assert ":hasParent" in results
        assert ":hasMother" in results
        assert ":likes" in results
        assert ":hasCreator" in results
        assert ":hasPet" in results

    def test_search_by_role_data_property(self, ont):
        axioms.add(ont, AXIOMS)
        results = _search_entities_role(ont, EntityType.DATA_PROPERTY)
        assert ":hasAge" in results
        assert ":hasName" in results
        assert ":hasWeight" in results
        assert ":hasMeasurement" in results
        assert ":fullName" in results
        assert ":hasSSN" in results

    def test_search_by_role_annotation_property(self, ont):
        axioms.add(ont, AXIOMS)
        results = _search_entities_role(ont, EntityType.ANNOTATION_PROPERTY)
        assert "rdfs:label" in results
        assert "rdfs:comment" in results
        assert "skos:definition" in results

    def test_search_by_role_named_individual(self, ont):
        axioms.add(ont, AXIOMS)
        results = _search_entities_role(ont, EntityType.NAMED_INDIVIDUAL)
        assert ":Alice" in results
        assert ":Bob" in results
        assert ":Fido" in results
        assert ":Rex" in results
        assert ":Whiskers" in results
        assert ":TheOne" in results
        assert ":Robert" in results

    def test_search_by_role_datatype(self, ont):
        axioms.add(ont, AXIOMS)
        results = _search_entities_role(ont, EntityType.DATATYPE)
        assert "ex:PositiveAge" in results

    def test_search_by_namespace(self, ont):
        axioms.add(ont, AXIOMS)
        default_ns = _search_entities_ns(ont, "")
        # All :-prefixed entities
        assert ":Dog" in default_ns
        assert ":Alice" in default_ns
        assert ":owns" in default_ns
        # Other namespace
        rdfs_ns = _search_entities_ns(ont, "rdfs")
        assert "rdfs:label" in rdfs_ns
        assert "rdfs:comment" in rdfs_ns
        assert ":Dog" not in rdfs_ns

    def test_search_combined_query_and_role(self, ont):
        axioms.add(ont, AXIOMS)
        # Search "Dog" but only classes
        page = entities.search(ont, query="Dog", role=EntityType.CLASS, limit=1000)
        iris = {str(m.iri) for m in page.matches}
        assert ":Dog" in iris
        # :Fido (individual) should not match even though it's a Dog instance
        assert ":Fido" not in iris

    def test_search_combined_query_and_namespace(self, ont):
        axioms.add(ont, AXIOMS)
        page = entities.search(ont, query="label", namespace="rdfs", limit=1000)
        iris = {str(m.iri) for m in page.matches}
        assert "rdfs:label" in iris
        # skos:definition should not match (wrong namespace)
        assert "skos:definition" not in iris

    def test_search_match_quality_ordering(self, ont):
        axioms.add(ont, AXIOMS)
        # "Dog" should match :Dog as exact (local_name) before substring matches
        page = entities.search(ont, query="Dog", limit=1000)
        if page.matches:
            first = page.matches[0]
            assert str(first.iri) == ":Dog"
            assert first.match_quality == "exact"

    def test_search_returns_annotations(self, ont):
        axioms.add(ont, AXIOMS)
        page = entities.search(ont, query="Dog", limit=1000)
        dog_match = next(m for m in page.matches if str(m.iri) == ":Dog")
        ann_values = {a.value for a in dog_match.annotations}
        assert "Dog" in ann_values
        assert "Hund" in ann_values

    def test_search_returns_roles(self, ont):
        axioms.add(ont, AXIOMS)
        page = entities.search(ont, query="Dog", limit=1000)
        dog_match = next(m for m in page.matches if str(m.iri) == ":Dog")
        assert EntityType.CLASS in dog_match.roles

    def test_pagination(self, ont):
        axioms.add(ont, AXIOMS)
        all_results = _all_entity_iris(ont)
        total = len(all_results)
        assert total > 5, "Need enough entities to test pagination"

        # Collect all pages
        collected = set()
        offset = 0
        page_size = 5
        while True:
            page = entities.search(ont, limit=page_size, offset=offset)
            if not page.matches:
                break
            for m in page.matches:
                collected.add(str(m.iri))
            assert page.total == total
            offset += page_size

        assert collected == all_results

    def test_text_pagination(self, ont):
        axioms.add(ont, AXIOMS)
        # "has" matches many entities by local_name substring
        full = entities.search(ont, query="has", limit=1000)
        assert full.total > 3

        collected = set()
        offset = 0
        while True:
            page = entities.search(ont, query="has", limit=3, offset=offset)
            if not page.matches:
                break
            for m in page.matches:
                collected.add(str(m.iri))
            offset += 3

        assert len(collected) == full.total


class TestSearchAxiomsComprehensive:
    """Verify every axiom is findable through all applicable search paths."""

    def test_all_axiom_types_searchable(self, ont):
        result = axioms.add(ont, AXIOMS)
        added_types = {ha.axiom.type for ha in result.added}

        for axiom_type in added_types:
            found = _search_axioms_type(ont, axiom_type)
            assert len(found) > 0, f"No axioms found for type {axiom_type}"

    def test_search_by_each_axiom_type_count(self, ont):
        axioms.add(ont, AXIOMS)
        expected_type_counts = {}
        for ax in AXIOMS:
            expected_type_counts[ax.type] = expected_type_counts.get(ax.type, 0) + 1

        for axiom_type, expected in expected_type_counts.items():
            found = _search_axioms_type(ont, axiom_type)
            assert len(found) == expected, (
                f"Type {axiom_type}: expected {expected}, got {len(found)}"
            )

    def test_search_axioms_by_iri_finds_all_mentioning_axioms(self, ont):
        axioms.add(ont, AXIOMS)

        # :Dog appears in: 2 Declarations? No, 1. Plus labels, SubClassOf, DisjointClasses, ClassAssertion
        dog_axioms = _search_axioms_iri(ont, ":Dog")
        dog_types = {ha.axiom.type for ha in dog_axioms}
        assert "Declaration" in dog_types
        assert "AnnotationAssertion" in dog_types
        assert "SubClassOf" in dog_types
        assert "DisjointClasses" in dog_types

        # :Alice appears in many ABox axioms
        alice_axioms = _search_axioms_iri(ont, ":Alice")
        alice_types = {ha.axiom.type for ha in alice_axioms}
        assert "Declaration" in alice_types
        assert "AnnotationAssertion" in alice_types
        assert "ClassAssertion" in alice_types
        assert "ObjectPropertyAssertion" in alice_types
        assert "NegativeObjectPropertyAssertion" in alice_types
        assert "DataPropertyAssertion" in alice_types
        assert "NegativeDataPropertyAssertion" in alice_types
        assert "DifferentIndividuals" in alice_types

    def test_search_axioms_by_iri_for_properties(self, ont):
        axioms.add(ont, AXIOMS)

        # :hasPart appears in: Declaration, SubClassOf (via expression), TransitiveObjectProperty,
        # ReflexiveObjectProperty
        part_axioms = _search_axioms_iri(ont, ":hasPart")
        part_types = {ha.axiom.type for ha in part_axioms}
        assert "Declaration" in part_types
        assert "TransitiveObjectProperty" in part_types
        assert "ReflexiveObjectProperty" in part_types
        assert "SubClassOf" in part_types  # via ObjectSomeValuesFrom

    def test_search_axioms_by_iri_for_data_properties(self, ont):
        axioms.add(ont, AXIOMS)

        age_axioms = _search_axioms_iri(ont, ":hasAge")
        age_types = {ha.axiom.type for ha in age_axioms}
        assert "Declaration" in age_types
        assert "DataPropertyDomain" in age_types
        assert "DataPropertyRange" in age_types
        assert "FunctionalDataProperty" in age_types
        assert "DataPropertyAssertion" in age_types
        assert "NegativeDataPropertyAssertion" in age_types

    def test_search_axioms_by_annotation_query(self, ont):
        axioms.add(ont, AXIOMS)

        # The SubClassOf(Dog, Mammal) has an axiom-level annotation "Dogs are mammals obviously"
        found = _search_axioms_ann(ont, "mammals obviously")
        assert len(found) == 1
        assert found[0].axiom.type == "SubClassOf"

    def test_search_axioms_combined_iri_and_type(self, ont):
        axioms.add(ont, AXIOMS)

        # :Dog SubClassOf axioms only
        page = axioms.search(ont, iri=IRI(":Dog"), axiom_types=["SubClassOf"], limit=1000)
        for ha in page.axioms:
            assert ha.axiom.type == "SubClassOf"
        assert len(page.axioms) >= 3  # Dog < Animal, Dog < Pet, Dog < Mammal

    def test_search_axioms_combined_iri_and_annotation(self, ont):
        axioms.add(ont, AXIOMS)

        # Search :Dog axioms that also have annotation containing "mammals"
        page = axioms.search(ont, iri=IRI(":Dog"), annotation_query="mammals", limit=1000)
        assert len(page.axioms) == 1
        assert page.axioms[0].axiom.type == "SubClassOf"

    def test_search_axioms_combined_all_three(self, ont):
        axioms.add(ont, AXIOMS)

        page = axioms.search(
            ont,
            iri=IRI(":Dog"),
            axiom_types=["SubClassOf"],
            annotation_query="mammals",
            limit=1000,
        )
        assert len(page.axioms) == 1

    def test_search_axioms_pagination(self, ont):
        axioms.add(ont, AXIOMS)

        full = axioms.search(ont, limit=1000)
        total = full.total
        assert total == len(AXIOMS)

        collected_hashes = set()
        offset = 0
        while True:
            page = axioms.search(ont, limit=5, offset=offset)
            if not page.axioms:
                break
            for ha in page.axioms:
                collected_hashes.add(ha.hash)
            offset += 5

        assert len(collected_hashes) == total

    def test_no_false_positives_type_filter(self, ont):
        axioms.add(ont, AXIOMS)

        # Searching for a type with no axioms returns empty
        page = axioms.search(ont, axiom_types=["SubObjectPropertyOfChain"], limit=1000)
        for ha in page.axioms:
            assert ha.axiom.type == "SubObjectPropertyOfChain"

    def test_search_axioms_by_iri_entity_in_expression_only(self, ont):
        axioms.add(ont, AXIOMS)

        # :Heart appears only inside an ObjectSomeValuesFrom expression
        heart_axioms = _search_axioms_iri(ont, ":Heart")
        assert len(heart_axioms) >= 1
        assert any(ha.axiom.type == "SubClassOf" for ha in heart_axioms)

    def test_search_axioms_by_iri_entity_in_chain(self, ont):
        axioms.add(ont, AXIOMS)

        # :hasBrother appears only in SubObjectPropertyOfChain
        brother_axioms = _search_axioms_iri(ont, ":hasBrother")
        assert len(brother_axioms) >= 1
        assert any(ha.axiom.type == "SubObjectPropertyOfChain" for ha in brother_axioms)


class TestGetEntityComprehensive:
    """Verify get_entity returns correct roles, annotations, and axiom counts."""

    def test_get_class_entity(self, ont):
        axioms.add(ont, AXIOMS)
        info = entities.get(ont, IRI(":Dog"))
        assert info is not None
        assert EntityType.CLASS in info.roles
        ann_values = {a.value for a in info.annotations}
        assert "Dog" in ann_values
        assert "Hund" in ann_values
        assert info.axiom_counts["SubClassOf"] >= 3
        assert info.axiom_counts["DisjointClasses"] >= 1

    def test_get_individual_entity(self, ont):
        axioms.add(ont, AXIOMS)
        info = entities.get(ont, IRI(":Alice"))
        assert info is not None
        assert EntityType.NAMED_INDIVIDUAL in info.roles
        ann_values = {a.value for a in info.annotations}
        assert "Alice Smith" in ann_values

    def test_get_object_property_entity(self, ont):
        axioms.add(ont, AXIOMS)
        info = entities.get(ont, IRI(":owns"))
        assert info is not None
        assert EntityType.OBJECT_PROPERTY in info.roles
        assert info.axiom_counts["ObjectPropertyDomain"] >= 1
        assert info.axiom_counts["ObjectPropertyRange"] >= 1

    def test_get_data_property_entity(self, ont):
        axioms.add(ont, AXIOMS)
        info = entities.get(ont, IRI(":hasAge"))
        assert info is not None
        assert EntityType.DATA_PROPERTY in info.roles
        assert info.axiom_counts["DataPropertyDomain"] >= 1
        assert info.axiom_counts["DataPropertyRange"] >= 1
        assert info.axiom_counts["FunctionalDataProperty"] >= 1

    def test_get_nonexistent_entity(self, ont):
        axioms.add(ont, AXIOMS)
        assert entities.get(ont, IRI(":Nonexistent")) is None

    def test_annotation_counts_exclude_annotation_assertions(self, ont):
        axioms.add(ont, AXIOMS)
        # get_entity axiom_counts should NOT include AnnotationAssertion
        info = entities.get(ont, IRI(":Dog"))
        assert info is not None
        assert "AnnotationAssertion" not in info.axiom_counts


class TestAnnotateAndSearch:
    """Verify annotated axioms are searchable by annotation content."""

    def test_annotate_then_search(self, ont):
        axioms.add(ont, AXIOMS)

        # Find the Dog < Animal SubClassOf axiom
        page = axioms.search(ont, iri=IRI(":Dog"), axiom_types=["SubClassOf"], limit=1000)
        dog_animal = None
        for ha in page.axioms:
            ax = ha.axiom
            if (
                hasattr(ax, "sub_class")
                and hasattr(ax.sub_class, "iri")
                and str(ax.sub_class.iri) == ":Dog"
                and hasattr(ax, "super_class")
                and hasattr(ax.super_class, "iri")
                and str(ax.super_class.iri) == ":Animal"
            ):
                dog_animal = ha
                break
        assert dog_animal is not None

        # Annotate it
        axioms.annotate(
            ont,
            dog_animal.hash,
            add_annotations=[
                Annotation(
                    property=IRI("rdfs:comment"),
                    value=LangLiteral(value="canines are a subset of animals"),
                )
            ],
        )

        # Now search for it by annotation
        found = _search_axioms_ann(ont, "canines are a subset")
        assert len(found) == 1
        assert found[0].hash == dog_animal.hash

    def test_remove_annotation_then_search_fails(self, ont):
        axioms.add(ont, AXIOMS)

        # The Dog < Mammal axiom already has an annotation
        page = axioms.search(ont, iri=IRI(":Dog"), annotation_query="mammals obviously", limit=1000)
        assert len(page.axioms) == 1
        ha = page.axioms[0]

        # Remove that annotation
        axioms.annotate(
            ont,
            ha.hash,
            remove_annotations=[
                Annotation(
                    property=IRI("rdfs:comment"),
                    value=LangLiteral(value="Dogs are mammals obviously"),
                )
            ],
        )

        # Should no longer be findable
        found = _search_axioms_ann(ont, "mammals obviously")
        assert len(found) == 0


class TestEdgeCases:
    """Edge cases for search."""

    def test_empty_store_search(self, ont):
        page = entities.search(ont, query="anything", limit=50)
        assert page.matches == []
        assert page.total == 0

    def test_empty_store_axiom_search(self, ont):
        page = axioms.search(ont, limit=50)
        assert page.axioms == []
        assert page.total == 0

    def test_no_results_query(self, ont):
        axioms.add(ont, AXIOMS)
        page = entities.search(ont, query="xyzzy_nonexistent_12345", limit=50)
        assert page.matches == []

    def test_case_insensitive_search(self, ont):
        axioms.add(ont, AXIOMS)
        # Search is case-insensitive
        upper = _search_entities_text(ont, "DOG")
        lower = _search_entities_text(ont, "Dog")
        mixed = _search_entities_text(ont, "dOg")
        assert ":Dog" in upper
        assert ":Dog" in lower
        assert ":Dog" in mixed

    def test_search_with_colon_in_query(self, ont):
        axioms.add(ont, AXIOMS)
        # Searching for a full IRI-like string
        _search_entities_text(ont, ":Dog")

    def test_multiple_axiom_types_filter(self, ont):
        axioms.add(ont, AXIOMS)
        page = axioms.search(ont, axiom_types=["SubClassOf", "DisjointClasses"], limit=1000)
        types = {ha.axiom.type for ha in page.axioms}
        assert types <= {"SubClassOf", "DisjointClasses"}
        assert "SubClassOf" in types
        assert "DisjointClasses" in types

    def test_total_count_matches_actual(self, ont):
        axioms.add(ont, AXIOMS)
        page = axioms.search(ont, limit=1)
        assert page.total == len(AXIOMS)
        # Only 1 axiom returned but total is correct
        assert len(page.axioms) == 1
