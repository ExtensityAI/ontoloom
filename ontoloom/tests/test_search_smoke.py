"""Exhaustive smoke test for search_entities.

Builds a realistic ontology with diverse axiom types, then verifies that
every entity is discoverable through the applicable search paths.
"""

import tempfile
from pathlib import Path

import pytest
from ontoloom.axioms.store import add_axioms
from ontoloom.connection import Ontology, Session
from ontoloom.entities.store import (
    EntityNotFoundError,
    collect_entity_iris,
    get_entity,
    search_entities,
)
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import (
    AnnotationAssertion,
    AnnotationPropertyDomain,
    AnnotationPropertyRange,
    ClassAssertion,
    DataPropertyAssertion,
    DataPropertyDomain,
    DataPropertyRange,
    DatatypeDefinition,
    Declaration,
    DifferentIndividuals,
    DisjointClasses,
    EquivalentClasses,
    EquivalentDataProperties,
    EquivalentObjectProperties,
    FunctionalDataProperty,
    HasKey,
    NegativeDataPropertyAssertion,
    NegativeObjectPropertyAssertion,
    ObjectPropertyAssertion,
    ObjectPropertyDomain,
    ObjectPropertyRange,
    ReflexiveObjectProperty,
    SameIndividual,
    SubAnnotationPropertyOf,
    SubClassOf,
    SubDataPropertyOf,
    SubObjectPropertyOf,
    SubObjectPropertyOfChain,
    TransitiveObjectProperty,
)
from ontoloom.owl.expressions import (
    DataHasValue,
    DataSomeValuesFrom,
    ObjectHasSelf,
    ObjectHasValue,
    ObjectIntersectionOf,
    ObjectOneOf,
    ObjectSomeValuesFrom,
)
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import (
    DataOneOf,
    DataType,
    DataTypeRef,
    LangLiteral,
    TypedLiteral,
)
from ontoloom.owl.markers import EntityType
from ontoloom.transactions import atomic


@pytest.fixture
def s():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.db"
        Ontology.create(path)
        with atomic(Ontology(path)) as session:
            yield session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def nc(iri: str) -> IRI:
    return IRI(iri)


def _all_entity_iris(s: Session) -> set[str]:
    """Collect all entity IRIs via list-all search."""
    iris = set()
    page = search_entities(s, limit=1000)
    for m in page.matches:
        iris.add(str(m.iri))
    return iris


def _search_entities_text(s: Session, query: str) -> set[str]:
    page = search_entities(s, query=query, limit=1000)
    return {str(m.iri) for m in page.matches}


def _search_entities_role(s: Session, role: str) -> set[str]:
    page = search_entities(s, role=role, limit=1000)
    return {str(m.iri) for m in page.matches}


def _search_entities_ns(s: Session, namespace: str) -> set[str]:
    page = search_entities(s, namespace=namespace, limit=1000)
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
        super_class=DataSomeValuesFrom(
            property=IRI(":hasAge"), range=DataTypeRef(datatype=DataType.INTEGER)
        ),
    ),
    SubClassOf(
        sub_class=nc(":Person"),
        super_class=ObjectIntersectionOf(operands=(nc(":Animal"), nc(":Rational"))),
    ),
    # --- EquivalentClasses ---
    EquivalentClasses(
        equivalent_classes=(
            nc(":Mother"),
            ObjectIntersectionOf(operands=(nc(":Woman"), nc(":Parent"))),
        ),
    ),
    # --- DisjointClasses ---
    DisjointClasses(disjoint_classes=(nc(":Dog"), nc(":Cat"))),
    # --- Object property axioms ---
    SubObjectPropertyOf(
        sub_object_property=IRI(":hasMother"), super_object_property=IRI(":hasParent")
    ),
    SubObjectPropertyOfChain(
        chain=(IRI(":hasParent"), IRI(":hasBrother")),
        super_property=IRI(":hasUncle"),
    ),
    EquivalentObjectProperties(object_properties=(IRI(":owns"), IRI(":hasPet"))),
    TransitiveObjectProperty(transitive_property=IRI(":hasPart")),
    ReflexiveObjectProperty(reflexive_property=IRI(":hasPart")),
    ObjectPropertyDomain(object_property=IRI(":owns"), domain=nc(":Person")),
    ObjectPropertyRange(object_property=IRI(":owns"), range=nc(":Animal")),
    # --- Data property axioms ---
    SubDataPropertyOf(
        sub_data_property=IRI(":hasWeight"), super_data_property=IRI(":hasMeasurement")
    ),
    EquivalentDataProperties(data_properties=(IRI(":hasName"), IRI(":fullName"))),
    DataPropertyDomain(data_property=IRI(":hasAge"), domain=nc(":Person")),
    DataPropertyRange(
        data_property=IRI(":hasAge"), range=DataTypeRef(datatype=DataType.NON_NEGATIVE_INTEGER)
    ),
    FunctionalDataProperty(functional_property=IRI(":hasAge")),
    # --- HasKey ---
    HasKey(
        class_expression=nc(":Person"),
        object_properties=(),
        data_properties=(IRI(":hasSSN"),),
    ),
    # --- Annotation property axioms ---
    SubAnnotationPropertyOf(
        sub_annotation_property=IRI("skos:definition"),
        super_annotation_property=IRI("rdfs:comment"),
    ),
    AnnotationPropertyDomain(annotation_property=IRI("rdfs:label"), domain=IRI("owl:Thing")),
    AnnotationPropertyRange(annotation_property=IRI("rdfs:label"), range=IRI("rdfs:Literal")),
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
    SameIndividual(same_individuals=(IRI(":Bob"), IRI(":Robert"))),
    DifferentIndividuals(different_individuals=(IRI(":Alice"), IRI(":Bob"))),
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
        super_class=ObjectHasSelf(self_property=IRI(":likes")),
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

    def test_all_declared_entities_are_listed(self, s):
        add_axioms(s, AXIOMS)
        all_iris = _all_entity_iris(s)
        # Every Declaration IRI must appear
        for ax in AXIOMS:
            if isinstance(ax, Declaration):
                assert str(ax.iri) in all_iris, f"Declaration {ax.iri} not in entity list"

    def test_entities_from_expressions_are_listed(self, s):
        add_axioms(s, AXIOMS)
        all_iris = _all_entity_iris(s)
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

    def test_search_by_local_name_exact(self, s):
        add_axioms(s, AXIOMS)
        results = _search_entities_text(s, "Dog")
        assert ":Dog" in results

    def test_search_by_local_name_substring(self, s):
        add_axioms(s, AXIOMS)
        # "art" is substring of "hasPart"
        results = _search_entities_text(s, "art")
        assert ":hasPart" in results

    def test_search_by_annotation_value_exact(self, s):
        add_axioms(s, AXIOMS)
        # "Hund" is an exact rdfs:label value for :Dog
        results = _search_entities_text(s, "Hund")
        assert ":Dog" in results

    def test_search_by_annotation_value_substring(self, s):
        add_axioms(s, AXIOMS)
        # "living creature" is a substring of :Animal's rdfs:comment
        results = _search_entities_text(s, "living creature")
        assert ":Animal" in results

    def test_search_by_annotation_value_definition(self, s):
        add_axioms(s, AXIOMS)
        # :Pet has a skos:definition containing "domesticated"
        results = _search_entities_text(s, "domesticated")
        assert ":Pet" in results

    def test_search_individual_by_label(self, s):
        add_axioms(s, AXIOMS)
        results = _search_entities_text(s, "Alice Smith")
        assert ":Alice" in results

    def test_search_by_role_class(self, s):
        add_axioms(s, AXIOMS)
        results = _search_entities_role(s, EntityType.CLASS)
        assert ":Dog" in results
        assert ":Cat" in results
        assert ":Animal" in results
        assert ":Person" in results
        # Individuals should NOT appear
        assert ":Alice" not in results
        assert ":Fido" not in results

    def test_search_by_role_object_property(self, s):
        add_axioms(s, AXIOMS)
        results = _search_entities_role(s, EntityType.OBJECT_PROPERTY)
        assert ":owns" in results
        assert ":hasPart" in results
        assert ":hasParent" in results
        assert ":hasMother" in results
        assert ":likes" in results
        assert ":hasCreator" in results
        assert ":hasPet" in results

    def test_search_by_role_data_property(self, s):
        add_axioms(s, AXIOMS)
        results = _search_entities_role(s, EntityType.DATA_PROPERTY)
        assert ":hasAge" in results
        assert ":hasName" in results
        assert ":hasWeight" in results
        assert ":hasMeasurement" in results
        assert ":fullName" in results
        assert ":hasSSN" in results

    def test_search_by_role_annotation_property(self, s):
        add_axioms(s, AXIOMS)
        results = _search_entities_role(s, EntityType.ANNOTATION_PROPERTY)
        assert "rdfs:label" in results
        assert "rdfs:comment" in results
        assert "skos:definition" in results

    def test_search_by_role_named_individual(self, s):
        add_axioms(s, AXIOMS)
        results = _search_entities_role(s, EntityType.NAMED_INDIVIDUAL)
        assert ":Alice" in results
        assert ":Bob" in results
        assert ":Fido" in results
        assert ":Rex" in results
        assert ":Whiskers" in results
        assert ":TheOne" in results
        assert ":Robert" in results

    def test_search_by_role_datatype(self, s):
        add_axioms(s, AXIOMS)
        results = _search_entities_role(s, EntityType.DATATYPE)
        assert "ex:PositiveAge" in results

    def test_search_by_namespace(self, s):
        add_axioms(s, AXIOMS)
        default_ns = _search_entities_ns(s, "")
        # All :-prefixed entities
        assert ":Dog" in default_ns
        assert ":Alice" in default_ns
        assert ":owns" in default_ns
        # Other namespace
        rdfs_ns = _search_entities_ns(s, "rdfs")
        assert "rdfs:label" in rdfs_ns
        assert "rdfs:comment" in rdfs_ns
        assert ":Dog" not in rdfs_ns

    def test_search_combined_query_and_role(self, s):
        add_axioms(s, AXIOMS)
        # Search "Dog" but only classes
        page = search_entities(s, query="Dog", role=EntityType.CLASS, limit=1000)
        iris = {str(m.iri) for m in page.matches}
        assert ":Dog" in iris
        # :Fido (individual) should not match even though it's a Dog instance
        assert ":Fido" not in iris

    def test_search_combined_query_and_namespace(self, s):
        add_axioms(s, AXIOMS)
        page = search_entities(s, query="label", namespace="rdfs", limit=1000)
        iris = {str(m.iri) for m in page.matches}
        assert "rdfs:label" in iris
        # skos:definition should not match (wrong namespace)
        assert "skos:definition" not in iris

    def test_search_match_quality_ordering(self, s):
        add_axioms(s, AXIOMS)
        # "Dog" should match :Dog as exact (local_name) before substring matches
        page = search_entities(s, query="Dog", limit=1000)
        if page.matches:
            first = page.matches[0]
            assert str(first.iri) == ":Dog"
            assert first.match_quality == "exact"

    def test_search_returns_annotations(self, s):
        add_axioms(s, AXIOMS)
        page = search_entities(s, query="Dog", limit=1000)
        dog_match = next(m for m in page.matches if str(m.iri) == ":Dog")
        ann_values = {a.value for a in dog_match.annotations}
        assert "Dog" in ann_values
        assert "Hund" in ann_values

    def test_search_returns_roles(self, s):
        add_axioms(s, AXIOMS)
        page = search_entities(s, query="Dog", limit=1000)
        dog_match = next(m for m in page.matches if str(m.iri) == ":Dog")
        assert EntityType.CLASS in dog_match.roles

    def test_pagination(self, s):
        add_axioms(s, AXIOMS)
        all_results = _all_entity_iris(s)
        total = len(all_results)
        assert total > 5, "Need enough entities to test pagination"

        # Collect all pages
        collected = set()
        offset = 0
        page_size = 5
        while True:
            page = search_entities(s, limit=page_size, offset=offset)
            if not page.matches:
                break
            for m in page.matches:
                collected.add(str(m.iri))
            assert page.total == total
            offset += page_size

        assert collected == all_results

    def test_text_pagination(self, s):
        add_axioms(s, AXIOMS)
        # "has" matches many entities by local_name substring
        full = search_entities(s, query="has", limit=1000)
        assert full.total > 3

        collected = set()
        offset = 0
        while True:
            page = search_entities(s, query="has", limit=3, offset=offset)
            if not page.matches:
                break
            for m in page.matches:
                collected.add(str(m.iri))
            offset += 3

        assert len(collected) == full.total


class TestGetEntityComprehensive:
    """Verify get_entity returns correct roles, annotations, and axiom counts."""

    def test_get_class_entity(self, s):
        add_axioms(s, AXIOMS)
        info = get_entity(s, IRI(":Dog"))
        assert info is not None
        assert EntityType.CLASS in info.roles
        ann_values = {a.value for a in info.annotations}
        assert "Dog" in ann_values
        assert "Hund" in ann_values
        assert info.axiom_counts["SubClassOf"] >= 3
        assert info.axiom_counts["DisjointClasses"] >= 1

    def test_get_individual_entity(self, s):
        add_axioms(s, AXIOMS)
        info = get_entity(s, IRI(":Alice"))
        assert info is not None
        assert EntityType.NAMED_INDIVIDUAL in info.roles
        ann_values = {a.value for a in info.annotations}
        assert "Alice Smith" in ann_values

    def test_get_object_property_entity(self, s):
        add_axioms(s, AXIOMS)
        info = get_entity(s, IRI(":owns"))
        assert info is not None
        assert EntityType.OBJECT_PROPERTY in info.roles
        assert info.axiom_counts["ObjectPropertyDomain"] >= 1
        assert info.axiom_counts["ObjectPropertyRange"] >= 1

    def test_get_data_property_entity(self, s):
        add_axioms(s, AXIOMS)
        info = get_entity(s, IRI(":hasAge"))
        assert info is not None
        assert EntityType.DATA_PROPERTY in info.roles
        assert info.axiom_counts["DataPropertyDomain"] >= 1
        assert info.axiom_counts["DataPropertyRange"] >= 1
        assert info.axiom_counts["FunctionalDataProperty"] >= 1

    def test_get_nonexistent_entity(self, s):

        add_axioms(s, AXIOMS)
        with pytest.raises(EntityNotFoundError):
            get_entity(s, IRI(":Nonexistent"))

    def test_annotation_counts_exclude_annotation_assertions(self, s):
        add_axioms(s, AXIOMS)
        # get_entity axiom_counts should NOT include AnnotationAssertion
        info = get_entity(s, IRI(":Dog"))
        assert info is not None
        assert "AnnotationAssertion" not in info.axiom_counts


class TestEnhancedEntitySearch:
    """Tests for declared, properties, and exclude_deprecated filters."""

    def test_declared_true_list(self, s):
        add_axioms(s, AXIOMS)
        page = search_entities(s, declared=True, exclude_deprecated=False, limit=1000)
        declared_iris = {str(m.iri) for m in page.matches}
        # All Declaration IRIs should be present
        for ax in AXIOMS:
            if isinstance(ax, Declaration):
                assert str(ax.iri) in declared_iris, f"{ax.iri} should be declared"
        # Undeclared entities (only appear in expressions) should NOT be present
        assert ":Heart" not in declared_iris
        assert ":Rational" not in declared_iris
        assert ":TheOne" not in declared_iris

    def test_declared_false_list(self, s):
        add_axioms(s, AXIOMS)
        page = search_entities(s, declared=False, exclude_deprecated=False, limit=1000)
        undeclared_iris = {str(m.iri) for m in page.matches}
        # Entities only referenced in expressions, never declared
        assert ":Heart" in undeclared_iris
        assert ":Rational" in undeclared_iris
        assert ":TheOne" in undeclared_iris
        # Declared entities should NOT appear
        assert ":Dog" not in undeclared_iris
        assert ":Alice" not in undeclared_iris

    def test_declared_true_text_search(self, s):
        add_axioms(s, AXIOMS)
        # "has" matches many entities by local_name substring
        page = search_entities(s, query="has", declared=True, exclude_deprecated=False, limit=1000)
        iris = {str(m.iri) for m in page.matches}
        # Declared properties with "has" in the name
        assert ":hasAge" in iris
        assert ":hasPart" in iris
        # :hasCreator is NOT declared (only appears in ObjectHasValue expression)
        assert ":hasCreator" not in iris

    def test_declared_false_text_search(self, s):
        add_axioms(s, AXIOMS)
        page = search_entities(s, query="has", declared=False, exclude_deprecated=False, limit=1000)
        iris = {str(m.iri) for m in page.matches}
        # :hasCreator is undeclared
        assert ":hasCreator" in iris
        # :hasAge is declared, should NOT appear
        assert ":hasAge" not in iris

    def test_declared_none_returns_all(self, s):
        add_axioms(s, AXIOMS)
        all_page = search_entities(s, declared=None, exclude_deprecated=False, limit=1000)
        all_iris = {str(m.iri) for m in all_page.matches}
        # Both declared and undeclared
        assert ":Dog" in all_iris
        assert ":Heart" in all_iris

    def test_properties_filter_with_query(self, s):
        add_axioms(s, AXIOMS)
        # "Dog" appears in rdfs:label and as local_name. Restrict annotation search to rdfs:label.
        page = search_entities(
            s, query="Dog", properties=["rdfs:label"], exclude_deprecated=False, limit=1000
        )
        iris = {str(m.iri) for m in page.matches}
        # :Dog has rdfs:label "Dog", so it should match
        assert ":Dog" in iris

    def test_properties_filter_excludes_non_matching(self, s):
        add_axioms(s, AXIOMS)
        # "domesticated" appears in skos:definition for :Pet
        # Restrict to rdfs:label only -> should NOT find :Pet via annotation
        page = search_entities(
            s,
            query="domesticated",
            properties=["rdfs:label"],
            exclude_deprecated=False,
            limit=1000,
        )
        iris = {str(m.iri) for m in page.matches}
        assert ":Pet" not in iris

    def test_properties_filter_skos_definition(self, s):
        add_axioms(s, AXIOMS)
        # "domesticated" in skos:definition -> should find :Pet
        page = search_entities(
            s,
            query="domesticated",
            properties=["skos:definition"],
            exclude_deprecated=False,
            limit=1000,
        )
        iris = {str(m.iri) for m in page.matches}
        assert ":Pet" in iris

    def test_properties_filter_no_query(self, s):
        add_axioms(s, AXIOMS)
        # Without query: find entities that have skos:definition annotations
        page = search_entities(
            s, properties=["skos:definition"], exclude_deprecated=False, limit=1000
        )
        iris = {str(m.iri) for m in page.matches}
        # :Pet has skos:definition
        assert ":Pet" in iris
        # :Dog has rdfs:label but NOT skos:definition
        assert ":Dog" not in iris

    def test_exclude_deprecated_true(self, s):
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
        add_axioms(s, extra)

        # Default (exclude_deprecated=True): :Obsolete should be excluded
        page = search_entities(s, limit=1000)
        iris = {str(m.iri) for m in page.matches}
        assert ":Dog" in iris
        assert ":Obsolete" not in iris

    def test_exclude_deprecated_false(self, s):
        extra = [
            *AXIOMS,
            Declaration(entity_type=EntityType.CLASS, iri=IRI(":Obsolete")),
            AnnotationAssertion(
                property=IRI("owl:deprecated"),
                subject=IRI(":Obsolete"),
                value=TypedLiteral(value="true"),
            ),
        ]
        add_axioms(s, extra)

        # exclude_deprecated=False: :Obsolete should be included
        page = search_entities(s, exclude_deprecated=False, limit=1000)
        iris = {str(m.iri) for m in page.matches}
        assert ":Obsolete" in iris

    def test_exclude_deprecated_text_search(self, s):
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
        add_axioms(s, extra)

        # Text search for "Obsolete" with exclude_deprecated=True
        page = search_entities(s, query="Obsolete", exclude_deprecated=True, limit=1000)
        iris = {str(m.iri) for m in page.matches}
        assert ":Obsolete" not in iris

        # Text search with exclude_deprecated=False
        page2 = search_entities(s, query="Obsolete", exclude_deprecated=False, limit=1000)
        iris2 = {str(m.iri) for m in page2.matches}
        assert ":Obsolete" in iris2

    def test_collect_iris_declared(self, s):
        add_axioms(s, AXIOMS)
        declared_iris = collect_entity_iris(s, declared=True, exclude_deprecated=False)
        assert ":Dog" in declared_iris
        assert ":Heart" not in declared_iris

        undeclared_iris = collect_entity_iris(s, declared=False, exclude_deprecated=False)
        assert ":Heart" in undeclared_iris
        assert ":Dog" not in undeclared_iris

    def test_collect_iris_exclude_deprecated(self, s):
        extra = [
            *AXIOMS,
            Declaration(entity_type=EntityType.CLASS, iri=IRI(":Obsolete")),
            AnnotationAssertion(
                property=IRI("owl:deprecated"),
                subject=IRI(":Obsolete"),
                value=TypedLiteral(value="true"),
            ),
        ]
        add_axioms(s, extra)

        iris_excl = collect_entity_iris(s, exclude_deprecated=True)
        assert ":Obsolete" not in iris_excl
        assert ":Dog" in iris_excl

        iris_incl = collect_entity_iris(s, exclude_deprecated=False)
        assert ":Obsolete" in iris_incl

    def test_collect_iris_properties_with_query(self, s):
        add_axioms(s, AXIOMS)
        # "domesticated" in skos:definition for :Pet
        iris = collect_entity_iris(
            s, query="domesticated", properties=["skos:definition"], exclude_deprecated=False
        )
        assert ":Pet" in iris

        # Same query restricted to rdfs:label -> should not find :Pet
        iris2 = collect_entity_iris(
            s, query="domesticated", properties=["rdfs:label"], exclude_deprecated=False
        )
        assert ":Pet" not in iris2


# -- F-F14: text search tiebreaker ordering --


class TestTextSearchTiebreakers:
    """Pin all three sort keys: quality (exact<substring), source (iri<annotation), IRI."""

    def test_tiebreaker_ordering(self, s):
        # Build four entities that each match query "target" via a distinct (quality, source) tier.
        add_axioms(
            s,
            [
                # tier (0,0): exact IRI match -> local name IS "target"
                Declaration(entity_type=EntityType.CLASS, iri=IRI(":target")),
                # tier (0,1): exact annotation match -> local name does NOT contain "target"
                Declaration(entity_type=EntityType.CLASS, iri=IRI(":aaa")),
                AnnotationAssertion(
                    property=IRI("rdfs:label"),
                    subject=IRI(":aaa"),
                    value=LangLiteral(value="target"),
                ),
                # tier (1,0): substring IRI match -> local name contains but ≠ "target"
                Declaration(entity_type=EntityType.CLASS, iri=IRI(":target_extra")),
                # tier (1,1): substring annotation match -> annotation contains "target"
                Declaration(entity_type=EntityType.CLASS, iri=IRI(":zzz")),
                AnnotationAssertion(
                    property=IRI("rdfs:label"),
                    subject=IRI(":zzz"),
                    value=LangLiteral(value="has_target_in_label"),
                ),
            ],
        )

        page = search_entities(s, query="target", limit=100)
        iris = [str(m.iri) for m in page.matches]

        assert ":target" in iris
        assert ":aaa" in iris
        assert ":target_extra" in iris
        assert ":zzz" in iris

        idx_exact_iri = iris.index(":target")
        idx_exact_ann = iris.index(":aaa")
        idx_sub_iri = iris.index(":target_extra")
        idx_sub_ann = iris.index(":zzz")

        # Tiebreaker 1: exact before substring
        assert idx_exact_iri < idx_sub_iri
        assert idx_exact_ann < idx_sub_ann
        # Tiebreaker 2: iri-source before annotation-source within same quality
        assert idx_exact_iri < idx_exact_ann
        assert idx_sub_iri < idx_sub_ann
        # Combined: exact-iri < exact-ann < sub-iri < sub-ann
        assert idx_exact_iri < idx_exact_ann < idx_sub_iri < idx_sub_ann

        # Verify match metadata is set correctly
        match_map = {str(m.iri): m for m in page.matches}
        assert match_map[":target"].match_quality == "exact"
        assert match_map[":target"].match_source == "iri"
        assert match_map[":aaa"].match_quality == "exact"
        assert match_map[":aaa"].match_source == "annotation"
        assert match_map[":target_extra"].match_quality == "substring"
        assert match_map[":target_extra"].match_source == "iri"
        assert match_map[":zzz"].match_quality == "substring"
        assert match_map[":zzz"].match_source == "annotation"
