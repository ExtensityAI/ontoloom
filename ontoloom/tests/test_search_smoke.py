"""Exhaustive smoke test for find_entities.

Builds a realistic ontology with diverse axiom types, then verifies that
every entity is discoverable through the applicable search paths.
"""

import pytest
from ontoloom.axioms.mutations import add_axioms
from ontoloom.connection import Session
from ontoloom.entities.projections import batch_fetch_entity_display
from ontoloom.entities.reader import (
    EntityNotFoundError,
    find_entities,
    get_entity,
)
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import (
    AnnotationAssertion,
    AnnotationPropertyDomain,
    AnnotationPropertyRange,
    AxiomTag,
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
    BCP47Tag,
    DataOneOf,
    DataType,
    DataTypeRef,
    LangLiteral,
    TypedLiteral,
)
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes.types import PrefixName

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def nc(iri: str) -> IRI:
    return IRI(iri)


def _all_entity_iris(s: Session) -> set[str]:
    """Collect all entity IRIs via list-all search."""
    return {str(i) for i in find_entities(s)}


def _find_entities_text(s: Session, query: str) -> set[str]:
    return {str(i) for i in find_entities(s, query=query)}


def _find_entities_role(s: Session, role: EntityType) -> set[str]:
    return {str(i) for i in find_entities(s, role=role)}


def _find_entities_ns(s: Session, namespace: PrefixName) -> set[str]:
    return {str(i) for i in find_entities(s, namespace=namespace)}


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
        value=LangLiteral(value="Dog", lang=BCP47Tag("en")),
    ),
    AnnotationAssertion(
        property=IRI("rdfs:label"),
        subject=IRI(":Dog"),
        value=LangLiteral(value="Hund", lang=BCP47Tag("de")),
    ),
    AnnotationAssertion(
        property=IRI("rdfs:label"),
        subject=IRI(":Cat"),
        value=LangLiteral(value="Cat", lang=BCP47Tag("en")),
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
    EquivalentObjectProperties(equivalent_object_properties=(IRI(":owns"), IRI(":hasPet"))),
    TransitiveObjectProperty(transitive_property=IRI(":hasPart")),
    ReflexiveObjectProperty(reflexive_property=IRI(":hasPart")),
    ObjectPropertyDomain(object_property=IRI(":owns"), domain=nc(":Person")),
    ObjectPropertyRange(object_property=IRI(":owns"), range=nc(":Animal")),
    # --- Data property axioms ---
    SubDataPropertyOf(
        sub_data_property=IRI(":hasWeight"), super_data_property=IRI(":hasMeasurement")
    ),
    EquivalentDataProperties(equivalent_data_properties=(IRI(":hasName"), IRI(":fullName"))),
    DataPropertyDomain(data_property=IRI(":hasAge"), domain=nc(":Person")),
    DataPropertyRange(
        data_property=IRI(":hasAge"), range=DataTypeRef(datatype=DataType.NON_NEGATIVE_INTEGER)
    ),
    FunctionalDataProperty(functional_property=IRI(":hasAge")),
    # --- HasKey ---
    HasKey(
        class_expression=nc(":Person"),
        has_key_object_properties=(),
        has_key_data_properties=(IRI(":hasSSN"),),
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


class TestFindEntitiesComprehensive:
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
        results = _find_entities_text(s, "Dog")
        assert ":Dog" in results

    def test_search_by_local_name_substring(self, s):
        add_axioms(s, AXIOMS)
        # "art" is substring of "hasPart"
        results = _find_entities_text(s, "art")
        assert ":hasPart" in results

    def test_search_by_annotation_value_exact(self, s):
        add_axioms(s, AXIOMS)
        # "Hund" is an exact rdfs:label value for :Dog
        results = _find_entities_text(s, "Hund")
        assert ":Dog" in results

    def test_search_by_annotation_value_substring(self, s):
        add_axioms(s, AXIOMS)
        # "living creature" is a substring of :Animal's rdfs:comment
        results = _find_entities_text(s, "living creature")
        assert ":Animal" in results

    def test_search_by_annotation_value_definition(self, s):
        add_axioms(s, AXIOMS)
        # :Pet has a skos:definition containing "domesticated"
        results = _find_entities_text(s, "domesticated")
        assert ":Pet" in results

    def test_search_individual_by_label(self, s):
        add_axioms(s, AXIOMS)
        results = _find_entities_text(s, "Alice Smith")
        assert ":Alice" in results

    @pytest.mark.parametrize(
        ("role", "expected_includes", "expected_excludes"),
        [
            pytest.param(
                EntityType.CLASS,
                (":Dog", ":Cat", ":Animal", ":Person"),
                (":Alice", ":Fido"),
                id="class",
            ),
            pytest.param(
                EntityType.OBJECT_PROPERTY,
                (
                    ":owns",
                    ":hasPart",
                    ":hasParent",
                    ":hasMother",
                    ":likes",
                    ":hasCreator",
                    ":hasPet",
                ),
                (),
                id="object_property",
            ),
            pytest.param(
                EntityType.DATA_PROPERTY,
                (
                    ":hasAge",
                    ":hasName",
                    ":hasWeight",
                    ":hasMeasurement",
                    ":fullName",
                    ":hasSSN",
                ),
                (),
                id="data_property",
            ),
            pytest.param(
                EntityType.ANNOTATION_PROPERTY,
                ("rdfs:label", "rdfs:comment", "skos:definition"),
                (),
                id="annotation_property",
            ),
            pytest.param(
                EntityType.NAMED_INDIVIDUAL,
                (
                    ":Alice",
                    ":Bob",
                    ":Fido",
                    ":Rex",
                    ":Whiskers",
                    ":TheOne",
                    ":Robert",
                ),
                (),
                id="named_individual",
            ),
            pytest.param(
                EntityType.DATATYPE,
                ("ex:PositiveAge",),
                (),
                id="datatype",
            ),
        ],
    )
    def test_search_by_role(self, s, role, expected_includes, expected_excludes):
        add_axioms(s, AXIOMS)
        results = _find_entities_role(s, role)
        for iri in expected_includes:
            assert iri in results, f"{iri} should be in role={role} results"
        for iri in expected_excludes:
            assert iri not in results, f"{iri} should not be in role={role} results"

    def test_search_by_namespace(self, s):
        add_axioms(s, AXIOMS)
        rdfs_ns = _find_entities_ns(s, PrefixName("rdfs"))
        assert "rdfs:label" in rdfs_ns
        assert "rdfs:comment" in rdfs_ns
        assert ":Dog" not in rdfs_ns

    def test_search_combined_query_and_role(self, s):
        add_axioms(s, AXIOMS)
        # Search "Dog" but only classes
        iris = {str(i) for i in find_entities(s, query="Dog", role=EntityType.CLASS)}
        assert ":Dog" in iris
        # :Fido (individual) should not match even though it's a Dog instance
        assert ":Fido" not in iris

    def test_search_combined_query_and_namespace(self, s):
        add_axioms(s, AXIOMS)
        iris = {str(i) for i in find_entities(s, query="label", namespace=PrefixName("rdfs"))}
        assert "rdfs:label" in iris
        # skos:definition should not match (wrong namespace)
        assert "skos:definition" not in iris

    def test_search_match_quality_ordering(self, s):
        add_axioms(s, AXIOMS)
        # "Dog" should match :Dog as exact (local_name) before substring matches
        iris = find_entities(s, query="Dog")
        if iris:
            # :Dog is an exact local-name match, so it sorts ahead of every
            # substring match and lands first in the ordered result.
            assert str(iris[0]) == ":Dog"

    def test_search_returns_annotations(self, s):
        add_axioms(s, AXIOMS)
        iris = find_entities(s, query="Dog")
        assert IRI(":Dog") in iris
        display = batch_fetch_entity_display(s, [":Dog"])
        ann_values = {a.value for a in display[":Dog"].annotations}
        assert "Dog" in ann_values
        assert "Hund" in ann_values

    def test_search_returns_roles(self, s):
        add_axioms(s, AXIOMS)
        iris = find_entities(s, query="Dog")
        assert IRI(":Dog") in iris
        display = batch_fetch_entity_display(s, [":Dog"])
        assert EntityType.CLASS in display[":Dog"].roles

    def test_full_result_covers_all_entities(self, s):
        add_axioms(s, AXIOMS)
        all_results = _all_entity_iris(s)
        assert len(all_results) > 5, "Need enough entities to exercise the full feed"

        iris = {str(i) for i in find_entities(s)}
        assert iris == all_results

    def test_text_search_full_result(self, s):
        add_axioms(s, AXIOMS)
        # "has" matches many entities by local_name substring
        iris = find_entities(s, query="has")
        assert len(iris) > 3
        # No truncation: a repeat call returns the same set.
        assert {str(i) for i in find_entities(s, query="has")} == {str(i) for i in iris}


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
        assert info.axiom_counts[AxiomTag.SUB_CLASS_OF] >= 3
        assert info.axiom_counts[AxiomTag.DISJOINT_CLASSES] >= 1

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
        assert info.axiom_counts[AxiomTag.OBJECT_PROPERTY_DOMAIN] >= 1
        assert info.axiom_counts[AxiomTag.OBJECT_PROPERTY_RANGE] >= 1

    def test_get_data_property_entity(self, s):
        add_axioms(s, AXIOMS)
        info = get_entity(s, IRI(":hasAge"))
        assert info is not None
        assert EntityType.DATA_PROPERTY in info.roles
        assert info.axiom_counts[AxiomTag.DATA_PROPERTY_DOMAIN] >= 1
        assert info.axiom_counts[AxiomTag.DATA_PROPERTY_RANGE] >= 1
        assert info.axiom_counts[AxiomTag.FUNCTIONAL_DATA_PROPERTY] >= 1

    def test_get_nonexistent_entity(self, s):

        add_axioms(s, AXIOMS)
        with pytest.raises(EntityNotFoundError):
            get_entity(s, IRI(":Nonexistent"))

    def test_axiom_counts_include_annotation_assertions(self, s):
        # get_entity reports the full axiom-type breakdown including
        # AnnotationAssertion, matching describe_ontology's top-by-axiom-count.
        add_axioms(s, AXIOMS)
        info = get_entity(s, IRI(":Dog"))
        assert info is not None
        assert info.axiom_counts.get(AxiomTag.ANNOTATION_ASSERTION, 0) > 0


_OBSOLETE_AXIOMS = (
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
)


class TestEnhancedEntitySearch:
    """Tests for declared, properties, and exclude_deprecated filters."""

    @pytest.mark.parametrize(
        ("extra_axioms", "kwargs", "expected_includes", "expected_excludes"),
        [
            pytest.param(
                (),
                {"declared": True, "exclude_deprecated": False},
                (),  # Declaration loop handled separately in the test body
                (":Heart", ":Rational", ":TheOne"),
                id="declared_true_list",
            ),
            pytest.param(
                (),
                {"declared": False, "exclude_deprecated": False},
                (":Heart", ":Rational", ":TheOne"),
                (":Dog", ":Alice"),
                id="declared_false_list",
            ),
            pytest.param(
                (),
                {"query": "has", "declared": True, "exclude_deprecated": False},
                (":hasAge", ":hasPart"),
                (":hasCreator",),
                id="declared_true_text_search",
            ),
            pytest.param(
                (),
                {"query": "has", "declared": False, "exclude_deprecated": False},
                (":hasCreator",),
                (":hasAge",),
                id="declared_false_text_search",
            ),
            pytest.param(
                (),
                {"declared": None, "exclude_deprecated": False},
                (":Dog", ":Heart"),
                (),
                id="declared_none_returns_all",
            ),
            pytest.param(
                _OBSOLETE_AXIOMS,
                {},  # defaults: exclude_deprecated=True
                (":Dog",),
                (":Obsolete",),
                id="exclude_deprecated_true",
            ),
            pytest.param(
                _OBSOLETE_AXIOMS,
                {"exclude_deprecated": False},
                (":Obsolete",),
                (),
                id="exclude_deprecated_false",
            ),
            pytest.param(
                _OBSOLETE_AXIOMS,
                {"query": "Obsolete", "exclude_deprecated": True},
                (),
                (":Obsolete",),
                id="exclude_deprecated_text_search_excluded",
            ),
            pytest.param(
                _OBSOLETE_AXIOMS,
                {"query": "Obsolete", "exclude_deprecated": False},
                (":Obsolete",),
                (),
                id="exclude_deprecated_text_search_included",
            ),
        ],
    )
    def test_search_with_filter(
        self, s, extra_axioms, kwargs, expected_includes, expected_excludes
    ):
        add_axioms(s, [*AXIOMS, *extra_axioms])
        iris = {str(i) for i in find_entities(s, **kwargs)}
        # Special case: declared=True must cover every Declaration IRI in AXIOMS
        if kwargs.get("declared") is True and "query" not in kwargs:
            for ax in AXIOMS:
                if isinstance(ax, Declaration):
                    assert str(ax.iri) in iris, f"{ax.iri} should be declared"
        for iri in expected_includes:
            assert iri in iris, f"{iri} should be in results for kwargs={kwargs}"
        for iri in expected_excludes:
            assert iri not in iris, f"{iri} should not be in results for kwargs={kwargs}"

    def test_properties_filter_with_query(self, s):
        add_axioms(s, AXIOMS)
        # "Dog" appears in rdfs:label and as local_name. Restrict annotation search to rdfs:label.
        iris = {
            str(i)
            for i in find_entities(
                s, query="Dog", properties=[IRI("rdfs:label")], exclude_deprecated=False
            )
        }
        # :Dog has rdfs:label "Dog", so it should match
        assert ":Dog" in iris

    def test_properties_filter_excludes_non_matching(self, s):
        add_axioms(s, AXIOMS)
        # "domesticated" appears in skos:definition for :Pet
        # Restrict to rdfs:label only -> should NOT find :Pet via annotation
        iris = {
            str(i)
            for i in find_entities(
                s, query="domesticated", properties=[IRI("rdfs:label")], exclude_deprecated=False
            )
        }
        assert ":Pet" not in iris

    def test_properties_filter_skos_definition(self, s):
        add_axioms(s, AXIOMS)
        # "domesticated" in skos:definition -> should find :Pet
        iris = {
            str(i)
            for i in find_entities(
                s,
                query="domesticated",
                properties=[IRI("skos:definition")],
                exclude_deprecated=False,
            )
        }
        assert ":Pet" in iris

    def test_properties_filter_no_query(self, s):
        add_axioms(s, AXIOMS)
        # Without query: find entities that have skos:definition annotations
        iris = {
            str(i)
            for i in find_entities(s, properties=[IRI("skos:definition")], exclude_deprecated=False)
        }
        # :Pet has skos:definition
        assert ":Pet" in iris
        # :Dog has rdfs:label but NOT skos:definition
        assert ":Dog" not in iris

    def test_collect_iris_declared(self, s):
        add_axioms(s, AXIOMS)
        declared_iris = find_entities(s, declared=True, exclude_deprecated=False)
        assert IRI(":Dog") in declared_iris
        assert IRI(":Heart") not in declared_iris

        undeclared_iris = find_entities(s, declared=False, exclude_deprecated=False)
        assert IRI(":Heart") in undeclared_iris
        assert IRI(":Dog") not in undeclared_iris

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

        iris_excl = find_entities(s, exclude_deprecated=True)
        assert IRI(":Obsolete") not in iris_excl
        assert IRI(":Dog") in iris_excl

        iris_incl = find_entities(s, exclude_deprecated=False)
        assert IRI(":Obsolete") in iris_incl

    def test_collect_iris_properties_with_query(self, s):
        add_axioms(s, AXIOMS)
        # "domesticated" in skos:definition for :Pet
        iris = find_entities(
            s, query="domesticated", properties=[IRI("skos:definition")], exclude_deprecated=False
        )
        assert IRI(":Pet") in iris

        # Same query restricted to rdfs:label -> should not find :Pet
        iris2 = find_entities(
            s, query="domesticated", properties=[IRI("rdfs:label")], exclude_deprecated=False
        )
        assert IRI(":Pet") not in iris2


# -- F-F14: text search tiebreaker ordering --


class TestTextSearchTiebreakers:
    """Pin the four ranking ordinals the EntityTextMatches CASE collapses to.

    The single ordered CASE reproduces the old `(quality, source, iri)` Python
    sort: local-name claims the source if it matched there at all, and quality
    is taken *within* the winning source. The four reachable states, in final
    order: local-name-exact (0), annotation-exact (1), local-name-substring (2),
    annotation-substring (3).
    """

    def test_four_ordinal_states(self, s):
        # Build four entities, each matching query "target" via a distinct ordinal.
        add_axioms(
            s,
            [
                # ordinal 0: local-name exact -> local name IS "target"
                Declaration(entity_type=EntityType.CLASS, iri=IRI(":target")),
                # ordinal 1: annotation exact, no local-name match
                Declaration(entity_type=EntityType.CLASS, iri=IRI(":aaa")),
                AnnotationAssertion(
                    property=IRI("rdfs:label"),
                    subject=IRI(":aaa"),
                    value=LangLiteral(value="target"),
                ),
                # ordinal 2: local-name substring (contains but ≠ "target")
                Declaration(entity_type=EntityType.CLASS, iri=IRI(":target_extra")),
                # ordinal 3: annotation substring, no local-name match
                Declaration(entity_type=EntityType.CLASS, iri=IRI(":zzz")),
                AnnotationAssertion(
                    property=IRI("rdfs:label"),
                    subject=IRI(":zzz"),
                    value=LangLiteral(value="has_target_in_label"),
                ),
            ],
        )

        iris = [str(i) for i in find_entities(s, query="target")]

        assert ":target" in iris
        assert ":aaa" in iris
        assert ":target_extra" in iris
        assert ":zzz" in iris

        ln_exact = iris.index(":target")
        ann_exact = iris.index(":aaa")
        ln_substring = iris.index(":target_extra")
        ann_substring = iris.index(":zzz")

        # Final order: local-name-exact < annotation-exact < local-name-substring < annotation-substring
        assert ln_exact < ann_exact < ln_substring < ann_substring

    def test_local_name_substring_beats_annotation_exact_cross_case(self, s):
        # The crossed state: local-name matches as SUBSTRING *and* an annotation
        # matches EXACTLY. Local-name claims the source, so quality is taken there
        # (substring) -> ordinal 2, NOT ordinal 1 (annotation-exact). It must rank
        # AFTER a pure annotation-exact entity and BEFORE a pure annotation-substring.
        add_axioms(
            s,
            [
                # pure annotation-exact -> ordinal 1
                Declaration(entity_type=EntityType.CLASS, iri=IRI(":aaa")),
                AnnotationAssertion(
                    property=IRI("rdfs:label"),
                    subject=IRI(":aaa"),
                    value=LangLiteral(value="target"),
                ),
                # cross case: local-name substring + annotation exact -> ordinal 2
                Declaration(entity_type=EntityType.CLASS, iri=IRI(":target_cross")),
                AnnotationAssertion(
                    property=IRI("rdfs:label"),
                    subject=IRI(":target_cross"),
                    value=LangLiteral(value="target"),
                ),
                # pure annotation-substring -> ordinal 3
                Declaration(entity_type=EntityType.CLASS, iri=IRI(":zzz")),
                AnnotationAssertion(
                    property=IRI("rdfs:label"),
                    subject=IRI(":zzz"),
                    value=LangLiteral(value="has_target_in_label"),
                ),
            ],
        )

        iris = [str(i) for i in find_entities(s, query="target")]

        ann_exact = iris.index(":aaa")
        cross = iris.index(":target_cross")
        ann_substring = iris.index(":zzz")

        # cross ranks at ordinal 2 (local-name-substring), so: 1 < 2 < 3
        assert ann_exact < cross < ann_substring
