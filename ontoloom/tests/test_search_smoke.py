"""Exhaustive smoke test for search_entities.

Builds a realistic ontology with diverse axiom types, then verifies that
every entity is discoverable through the applicable search paths.
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
    EntityType,
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


class TestEnhancedEntitySearch:
    """Tests for declared, properties, and exclude_deprecated filters."""

    def test_declared_true_list(self, ont):
        axioms.add(ont, AXIOMS)
        page = entities.search(ont, declared=True, exclude_deprecated=False, limit=1000)
        declared_iris = {str(m.iri) for m in page.matches}
        # All Declaration IRIs should be present
        for ax in AXIOMS:
            if isinstance(ax, Declaration):
                assert str(ax.iri) in declared_iris, f"{ax.iri} should be declared"
        # Undeclared entities (only appear in expressions) should NOT be present
        assert ":Heart" not in declared_iris
        assert ":Rational" not in declared_iris
        assert ":TheOne" not in declared_iris

    def test_declared_false_list(self, ont):
        axioms.add(ont, AXIOMS)
        page = entities.search(ont, declared=False, exclude_deprecated=False, limit=1000)
        undeclared_iris = {str(m.iri) for m in page.matches}
        # Entities only referenced in expressions, never declared
        assert ":Heart" in undeclared_iris
        assert ":Rational" in undeclared_iris
        assert ":TheOne" in undeclared_iris
        # Declared entities should NOT appear
        assert ":Dog" not in undeclared_iris
        assert ":Alice" not in undeclared_iris

    def test_declared_true_text_search(self, ont):
        axioms.add(ont, AXIOMS)
        # "has" matches many entities by local_name substring
        page = entities.search(
            ont, query="has", declared=True, exclude_deprecated=False, limit=1000
        )
        iris = {str(m.iri) for m in page.matches}
        # Declared properties with "has" in the name
        assert ":hasAge" in iris
        assert ":hasPart" in iris
        # :hasCreator is NOT declared (only appears in ObjectHasValue expression)
        assert ":hasCreator" not in iris

    def test_declared_false_text_search(self, ont):
        axioms.add(ont, AXIOMS)
        page = entities.search(
            ont, query="has", declared=False, exclude_deprecated=False, limit=1000
        )
        iris = {str(m.iri) for m in page.matches}
        # :hasCreator is undeclared
        assert ":hasCreator" in iris
        # :hasAge is declared, should NOT appear
        assert ":hasAge" not in iris

    def test_declared_none_returns_all(self, ont):
        axioms.add(ont, AXIOMS)
        all_page = entities.search(ont, declared=None, exclude_deprecated=False, limit=1000)
        all_iris = {str(m.iri) for m in all_page.matches}
        # Both declared and undeclared
        assert ":Dog" in all_iris
        assert ":Heart" in all_iris

    def test_properties_filter_with_query(self, ont):
        axioms.add(ont, AXIOMS)
        # "Dog" appears in rdfs:label and as local_name. Restrict annotation search to rdfs:label.
        page = entities.search(
            ont, query="Dog", properties=["rdfs:label"], exclude_deprecated=False, limit=1000
        )
        iris = {str(m.iri) for m in page.matches}
        # :Dog has rdfs:label "Dog", so it should match
        assert ":Dog" in iris

    def test_properties_filter_excludes_non_matching(self, ont):
        axioms.add(ont, AXIOMS)
        # "domesticated" appears in skos:definition for :Pet
        # Restrict to rdfs:label only — should NOT find :Pet via annotation
        page = entities.search(
            ont,
            query="domesticated",
            properties=["rdfs:label"],
            exclude_deprecated=False,
            limit=1000,
        )
        iris = {str(m.iri) for m in page.matches}
        assert ":Pet" not in iris

    def test_properties_filter_skos_definition(self, ont):
        axioms.add(ont, AXIOMS)
        # "domesticated" in skos:definition — should find :Pet
        page = entities.search(
            ont,
            query="domesticated",
            properties=["skos:definition"],
            exclude_deprecated=False,
            limit=1000,
        )
        iris = {str(m.iri) for m in page.matches}
        assert ":Pet" in iris

    def test_properties_filter_no_query(self, ont):
        axioms.add(ont, AXIOMS)
        # Without query: find entities that have skos:definition annotations
        page = entities.search(
            ont, properties=["skos:definition"], exclude_deprecated=False, limit=1000
        )
        iris = {str(m.iri) for m in page.matches}
        # :Pet has skos:definition
        assert ":Pet" in iris
        # :Dog has rdfs:label but NOT skos:definition
        assert ":Dog" not in iris

    def test_exclude_deprecated_true(self, ont):
        # Add the standard fixture plus a deprecated entity
        extra = [
            *AXIOMS,
            Declaration(entity_type=EntityType.CLASS, iri=IRI(":Obsolete")),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI(":Obsolete"),
                value=LangLiteral(value="Obsolete Class"),
            ),
            AnnotationAssertion(
                property=IRI("owl:deprecated"),
                subject=IRI(":Obsolete"),
                value=TypedLiteral(value="true"),
            ),
        ]
        axioms.add(ont, extra)

        # Default (exclude_deprecated=True): :Obsolete should be excluded
        page = entities.search(ont, limit=1000)
        iris = {str(m.iri) for m in page.matches}
        assert ":Dog" in iris
        assert ":Obsolete" not in iris

    def test_exclude_deprecated_false(self, ont):
        extra = [
            *AXIOMS,
            Declaration(entity_type=EntityType.CLASS, iri=IRI(":Obsolete")),
            AnnotationAssertion(
                property=IRI("owl:deprecated"),
                subject=IRI(":Obsolete"),
                value=TypedLiteral(value="true"),
            ),
        ]
        axioms.add(ont, extra)

        # exclude_deprecated=False: :Obsolete should be included
        page = entities.search(ont, exclude_deprecated=False, limit=1000)
        iris = {str(m.iri) for m in page.matches}
        assert ":Obsolete" in iris

    def test_exclude_deprecated_text_search(self, ont):
        extra = [
            *AXIOMS,
            Declaration(entity_type=EntityType.CLASS, iri=IRI(":Obsolete")),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI(":Obsolete"),
                value=LangLiteral(value="Obsolete Class"),
            ),
            AnnotationAssertion(
                property=IRI("owl:deprecated"),
                subject=IRI(":Obsolete"),
                value=TypedLiteral(value="true"),
            ),
        ]
        axioms.add(ont, extra)

        # Text search for "Obsolete" with exclude_deprecated=True
        page = entities.search(ont, query="Obsolete", exclude_deprecated=True, limit=1000)
        iris = {str(m.iri) for m in page.matches}
        assert ":Obsolete" not in iris

        # Text search with exclude_deprecated=False
        page2 = entities.search(ont, query="Obsolete", exclude_deprecated=False, limit=1000)
        iris2 = {str(m.iri) for m in page2.matches}
        assert ":Obsolete" in iris2

    def test_collect_iris_declared(self, ont):
        axioms.add(ont, AXIOMS)
        declared_iris = entities.collect_iris(ont, declared=True, exclude_deprecated=False)
        assert ":Dog" in declared_iris
        assert ":Heart" not in declared_iris

        undeclared_iris = entities.collect_iris(ont, declared=False, exclude_deprecated=False)
        assert ":Heart" in undeclared_iris
        assert ":Dog" not in undeclared_iris

    def test_collect_iris_exclude_deprecated(self, ont):
        extra = [
            *AXIOMS,
            Declaration(entity_type=EntityType.CLASS, iri=IRI(":Obsolete")),
            AnnotationAssertion(
                property=IRI("owl:deprecated"),
                subject=IRI(":Obsolete"),
                value=TypedLiteral(value="true"),
            ),
        ]
        axioms.add(ont, extra)

        iris_excl = entities.collect_iris(ont, exclude_deprecated=True)
        assert ":Obsolete" not in iris_excl
        assert ":Dog" in iris_excl

        iris_incl = entities.collect_iris(ont, exclude_deprecated=False)
        assert ":Obsolete" in iris_incl

    def test_collect_iris_properties_with_query(self, ont):
        axioms.add(ont, AXIOMS)
        # "domesticated" in skos:definition for :Pet
        iris = entities.collect_iris(
            ont, query="domesticated", properties=["skos:definition"], exclude_deprecated=False
        )
        assert ":Pet" in iris

        # Same query restricted to rdfs:label — should not find :Pet
        iris2 = entities.collect_iris(
            ont, query="domesticated", properties=["rdfs:label"], exclude_deprecated=False
        )
        assert ":Pet" not in iris2
