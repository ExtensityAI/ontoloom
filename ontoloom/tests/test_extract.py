"""Direct unit tests for iter_axiom_entities — verify exact IRIs, roles, and positions."""

from ontoloom.ontology.extract import iter_axiom_entities
from ontoloom.ontology.models.assertions import (
    ClassAssertion,
    DataPropertyAssertion,
    DifferentIndividuals,
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
    Declaration,
    DisjointClasses,
    EquivalentClasses,
    EquivalentObjectProperties,
    FunctionalDataProperty,
    HasKey,
    ObjectPropertyDomain,
    ObjectPropertyRange,
    SubAnnotationPropertyOf,
    SubClassOf,
    SubDataPropertyOf,
    SubObjectPropertyOf,
    SubObjectPropertyOfChain,
    TransitiveObjectProperty,
)
from ontoloom.ontology.models.expressions import (
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
    DataType,
    DataTypeRef,
    EntityType,
    LangLiteral,
    Position,
    TypedLiteral,
)


def NC(iri: str):  # noqa: N802
    return NamedClass(iri=IRI(iri))


P = Position


def _entities(axiom):
    return [(str(iri), role, pos) for iri, role, pos in iter_axiom_entities(axiom)]


# -- Declarations --


def test_declaration():
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI(":Dog"))
    assert _entities(ax) == [(":Dog", EntityType.CLASS, P.ENTITY)]


# -- SubClassOf with expressions --


def test_subclassof_named():
    ax = SubClassOf(sub_class=NC(":Dog"), super_class=NC(":Animal"))
    entities = _entities(ax)
    assert (":Dog", EntityType.CLASS, P.SUB_CLASS) in entities
    assert (":Animal", EntityType.CLASS, P.SUPER_CLASS) in entities


def test_subclassof_with_some_values_from():
    ax = SubClassOf(
        sub_class=NC(":A"),
        super_class=ObjectSomeValuesFrom(property=IRI(":r"), filler=NC(":B")),
    )
    entities = _entities(ax)
    assert (":A", EntityType.CLASS, P.SUB_CLASS) in entities
    assert (":r", EntityType.OBJECT_PROPERTY, P.RESTRICTION_PROPERTY) in entities
    assert (":B", EntityType.CLASS, P.FILLER) in entities


def test_subclassof_with_intersection():
    ax = SubClassOf(
        sub_class=NC(":A"),
        super_class=ObjectIntersectionOf(operands=(NC(":B"), NC(":C"))),
    )
    entities = _entities(ax)
    assert (":B", EntityType.CLASS, P.SUPER_CLASS) in entities
    assert (":C", EntityType.CLASS, P.SUPER_CLASS) in entities


# -- Expression types --


def test_object_one_of():
    ax = SubClassOf(sub_class=NC(":A"), super_class=ObjectOneOf(individual=IRI(":x")))
    entities = _entities(ax)
    assert (":x", EntityType.NAMED_INDIVIDUAL, P.SUPER_CLASS) in entities


def test_object_has_value():
    ax = SubClassOf(
        sub_class=NC(":A"),
        super_class=ObjectHasValue(property=IRI(":r"), individual=IRI(":x")),
    )
    entities = _entities(ax)
    assert (":r", EntityType.OBJECT_PROPERTY, P.RESTRICTION_PROPERTY) in entities
    assert (":x", EntityType.NAMED_INDIVIDUAL, P.FILLER) in entities


def test_object_has_self():
    ax = SubClassOf(sub_class=NC(":A"), super_class=ObjectHasSelf(property=IRI(":r")))
    entities = _entities(ax)
    assert (":r", EntityType.OBJECT_PROPERTY, P.RESTRICTION_PROPERTY) in entities


def test_data_some_values_from():
    ax = SubClassOf(
        sub_class=NC(":A"),
        super_class=DataSomeValuesFrom(
            property=IRI(":dp"), range=DataTypeRef(value=DataType.INTEGER)
        ),
    )
    entities = _entities(ax)
    assert (":dp", EntityType.DATA_PROPERTY, P.RESTRICTION_PROPERTY) in entities


# -- Object property axioms --


def test_sub_object_property_of():
    ax = SubObjectPropertyOf(sub_property=IRI(":r"), super_property=IRI(":s"))
    entities = _entities(ax)
    assert (":r", EntityType.OBJECT_PROPERTY, P.SUB_PROPERTY) in entities
    assert (":s", EntityType.OBJECT_PROPERTY, P.SUPER_PROPERTY) in entities


def test_sub_object_property_of_chain():
    ax = SubObjectPropertyOfChain(chain=(IRI(":r1"), IRI(":r2")), super_property=IRI(":s"))
    entities = _entities(ax)
    assert (":r1", EntityType.OBJECT_PROPERTY, P.CHAIN_MEMBER) in entities
    assert (":r2", EntityType.OBJECT_PROPERTY, P.CHAIN_MEMBER) in entities
    assert (":s", EntityType.OBJECT_PROPERTY, P.SUPER_PROPERTY) in entities


def test_equivalent_object_properties():
    ax = EquivalentObjectProperties(properties=(IRI(":r"), IRI(":s")))
    entities = _entities(ax)
    assert (":r", EntityType.OBJECT_PROPERTY, P.MEMBER) in entities
    assert (":s", EntityType.OBJECT_PROPERTY, P.MEMBER) in entities


def test_transitive_object_property():
    ax = TransitiveObjectProperty(property=IRI(":r"))
    assert _entities(ax) == [(":r", EntityType.OBJECT_PROPERTY, P.PROPERTY)]


def test_object_property_domain():
    ax = ObjectPropertyDomain(property=IRI(":r"), domain=NC(":C"))
    entities = _entities(ax)
    assert (":r", EntityType.OBJECT_PROPERTY, P.PROPERTY) in entities
    assert (":C", EntityType.CLASS, P.DOMAIN) in entities


def test_object_property_range():
    ax = ObjectPropertyRange(property=IRI(":r"), range=NC(":C"))
    entities = _entities(ax)
    assert (":r", EntityType.OBJECT_PROPERTY, P.PROPERTY) in entities
    assert (":C", EntityType.CLASS, P.RANGE) in entities


# -- Data property axioms --


def test_sub_data_property_of():
    ax = SubDataPropertyOf(sub_property=IRI(":dp1"), super_property=IRI(":dp2"))
    entities = _entities(ax)
    assert (":dp1", EntityType.DATA_PROPERTY, P.SUB_PROPERTY) in entities
    assert (":dp2", EntityType.DATA_PROPERTY, P.SUPER_PROPERTY) in entities


def test_data_property_domain():
    ax = DataPropertyDomain(property=IRI(":dp"), domain=NC(":C"))
    entities = _entities(ax)
    assert (":dp", EntityType.DATA_PROPERTY, P.PROPERTY) in entities
    assert (":C", EntityType.CLASS, P.DOMAIN) in entities


def test_data_property_range():
    ax = DataPropertyRange(property=IRI(":dp"), range=DataTypeRef(value=DataType.INTEGER))
    entities = _entities(ax)
    assert (":dp", EntityType.DATA_PROPERTY, P.PROPERTY) in entities


def test_functional_data_property():
    ax = FunctionalDataProperty(property=IRI(":dp"))
    assert _entities(ax) == [(":dp", EntityType.DATA_PROPERTY, P.PROPERTY)]


def test_has_key():
    ax = HasKey(
        class_expression=NC(":C"),
        object_properties=(IRI(":op"),),
        data_properties=(IRI(":dp"),),
    )
    entities = _entities(ax)
    assert (":C", EntityType.CLASS, P.CLASS) in entities
    assert (":op", EntityType.OBJECT_PROPERTY, P.PROPERTY) in entities
    assert (":dp", EntityType.DATA_PROPERTY, P.PROPERTY) in entities


# -- Annotation axioms --


def test_annotation_assertion_with_lang_literal():
    ax = AnnotationAssertion(
        property=IRI("rdfs:label"), subject=IRI(":Dog"), value=LangLiteral(value="Dog")
    )
    entities = _entities(ax)
    assert ("rdfs:label", EntityType.ANNOTATION_PROPERTY, P.PROPERTY) in entities
    assert (":Dog", None, P.SUBJECT) in entities


def test_annotation_assertion_with_iri_value():
    ax = AnnotationAssertion(
        property=IRI("rdfs:seeAlso"), subject=IRI(":Dog"), value=IRI("ex:DogPage")
    )
    entities = _entities(ax)
    assert ("rdfs:seeAlso", EntityType.ANNOTATION_PROPERTY, P.PROPERTY) in entities
    assert (":Dog", None, P.SUBJECT) in entities
    assert ("ex:DogPage", None, P.VALUE) in entities


def test_sub_annotation_property_of():
    ax = SubAnnotationPropertyOf(
        sub_property=IRI("skos:definition"), super_property=IRI("rdfs:comment")
    )
    entities = _entities(ax)
    assert ("skos:definition", EntityType.ANNOTATION_PROPERTY, P.SUB_PROPERTY) in entities
    assert ("rdfs:comment", EntityType.ANNOTATION_PROPERTY, P.SUPER_PROPERTY) in entities


def test_annotation_property_domain():
    ax = AnnotationPropertyDomain(property=IRI("rdfs:label"), domain=IRI("owl:Thing"))
    entities = _entities(ax)
    assert ("rdfs:label", EntityType.ANNOTATION_PROPERTY, P.PROPERTY) in entities
    assert ("owl:Thing", None, P.DOMAIN) in entities


def test_annotation_property_range():
    ax = AnnotationPropertyRange(property=IRI("rdfs:label"), range=IRI("rdfs:Literal"))
    entities = _entities(ax)
    assert ("rdfs:label", EntityType.ANNOTATION_PROPERTY, P.PROPERTY) in entities
    assert ("rdfs:Literal", None, P.RANGE) in entities


# -- ABox assertions --


def test_class_assertion():
    ax = ClassAssertion(class_expression=NC(":Dog"), individual=IRI(":Fido"))
    entities = _entities(ax)
    assert (":Dog", EntityType.CLASS, P.CLASS) in entities
    assert (":Fido", EntityType.NAMED_INDIVIDUAL, P.INDIVIDUAL) in entities


def test_object_property_assertion():
    ax = ObjectPropertyAssertion(property=IRI(":owns"), source=IRI(":Alice"), target=IRI(":Fido"))
    entities = _entities(ax)
    assert (":owns", EntityType.OBJECT_PROPERTY, P.PROPERTY) in entities
    assert (":Alice", EntityType.NAMED_INDIVIDUAL, P.SOURCE) in entities
    assert (":Fido", EntityType.NAMED_INDIVIDUAL, P.TARGET) in entities


def test_negative_object_property_assertion():
    ax = NegativeObjectPropertyAssertion(
        property=IRI(":owns"), source=IRI(":Alice"), target=IRI(":Rex")
    )
    entities = _entities(ax)
    assert (":owns", EntityType.OBJECT_PROPERTY, P.PROPERTY) in entities
    assert (":Alice", EntityType.NAMED_INDIVIDUAL, P.SOURCE) in entities
    assert (":Rex", EntityType.NAMED_INDIVIDUAL, P.TARGET) in entities


def test_data_property_assertion():
    ax = DataPropertyAssertion(
        property=IRI(":hasAge"),
        individual=IRI(":Alice"),
        value=TypedLiteral(value="30", datatype=DataType.INTEGER),
    )
    entities = _entities(ax)
    assert (":hasAge", EntityType.DATA_PROPERTY, P.PROPERTY) in entities
    assert (":Alice", EntityType.NAMED_INDIVIDUAL, P.INDIVIDUAL) in entities


def test_same_individual():
    ax = SameIndividual(individuals=(IRI(":Bob"), IRI(":Robert")))
    entities = _entities(ax)
    assert (":Bob", EntityType.NAMED_INDIVIDUAL, P.MEMBER) in entities
    assert (":Robert", EntityType.NAMED_INDIVIDUAL, P.MEMBER) in entities


def test_different_individuals():
    ax = DifferentIndividuals(individuals=(IRI(":Alice"), IRI(":Bob")))
    entities = _entities(ax)
    assert (":Alice", EntityType.NAMED_INDIVIDUAL, P.MEMBER) in entities
    assert (":Bob", EntityType.NAMED_INDIVIDUAL, P.MEMBER) in entities


# -- Axiom-level annotations --


def test_axiom_level_annotation_property_extracted():
    ax = SubClassOf(
        sub_class=NC(":Dog"),
        super_class=NC(":Animal"),
        annotations=(Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note")),),
    )
    entities = _entities(ax)
    assert ("rdfs:comment", EntityType.ANNOTATION_PROPERTY, P.PROPERTY) in entities


def test_axiom_level_annotation_iri_value_extracted():
    ax = SubClassOf(
        sub_class=NC(":Dog"),
        super_class=NC(":Animal"),
        annotations=(Annotation(property=IRI("rdfs:seeAlso"), value=IRI("ex:Reference")),),
    )
    entities = _entities(ax)
    assert ("rdfs:seeAlso", EntityType.ANNOTATION_PROPERTY, P.PROPERTY) in entities
    assert ("ex:Reference", None, P.VALUE) in entities


# -- Set-semantic axioms --


def test_equivalent_classes():
    ax = EquivalentClasses(expressions=(NC(":A"), NC(":B")))
    entities = _entities(ax)
    assert (":A", EntityType.CLASS, P.MEMBER) in entities
    assert (":B", EntityType.CLASS, P.MEMBER) in entities


def test_disjoint_classes():
    ax = DisjointClasses(expressions=(NC(":A"), NC(":B")))
    entities = _entities(ax)
    assert (":A", EntityType.CLASS, P.MEMBER) in entities
    assert (":B", EntityType.CLASS, P.MEMBER) in entities


# ============================================================
# Position-specific tests
# ============================================================


class TestPositionSubClassOfNamed:
    """SubClassOf with named super_class assigns SUB_CLASS and SUPER_CLASS."""

    def test_exact_positions(self):
        ax = SubClassOf(sub_class=NC(":Dog"), super_class=NC(":Animal"))
        entities = _entities(ax)
        assert entities == [
            (":Dog", EntityType.CLASS, P.SUB_CLASS),
            (":Animal", EntityType.CLASS, P.SUPER_CLASS),
        ]


class TestPositionSubClassOfRestriction:
    """SubClassOf with ObjectSomeValuesFrom assigns SUB_CLASS, RESTRICTION_PROPERTY, FILLER."""

    def test_exact_positions(self):
        ax = SubClassOf(
            sub_class=NC(":Animal"),
            super_class=ObjectSomeValuesFrom(property=IRI(":hasPart"), filler=NC(":Heart")),
        )
        entities = _entities(ax)
        assert entities == [
            (":Animal", EntityType.CLASS, P.SUB_CLASS),
            (":hasPart", EntityType.OBJECT_PROPERTY, P.RESTRICTION_PROPERTY),
            (":Heart", EntityType.CLASS, P.FILLER),
        ]


class TestPositionSubClassOfIntersectionWithRestriction:
    """SubClassOf with ObjectIntersectionOf containing a restriction."""

    def test_exact_positions(self):
        ax = SubClassOf(
            sub_class=NC(":Dog"),
            super_class=ObjectIntersectionOf(
                operands=(
                    NC(":Animal"),
                    ObjectSomeValuesFrom(property=IRI(":hasPart"), filler=NC(":Tail")),
                )
            ),
        )
        entities = _entities(ax)
        assert entities == [
            (":Dog", EntityType.CLASS, P.SUB_CLASS),
            (":Animal", EntityType.CLASS, P.SUPER_CLASS),
            (":hasPart", EntityType.OBJECT_PROPERTY, P.RESTRICTION_PROPERTY),
            (":Tail", EntityType.CLASS, P.FILLER),
        ]


class TestPositionEquivalentClassesWithRestriction:
    """EquivalentClasses with a restriction assigns MEMBER, RESTRICTION_PROPERTY, FILLER."""

    def test_exact_positions(self):
        ax = EquivalentClasses(
            expressions=(
                NC(":Parent"),
                ObjectSomeValuesFrom(property=IRI(":hasChild"), filler=NC(":Person")),
            )
        )
        entities = _entities(ax)
        assert entities == [
            (":Parent", EntityType.CLASS, P.MEMBER),
            (":hasChild", EntityType.OBJECT_PROPERTY, P.RESTRICTION_PROPERTY),
            (":Person", EntityType.CLASS, P.FILLER),
        ]


class TestPositionAnnotationAssertion:
    """AnnotationAssertion assigns SUBJECT, PROPERTY, VALUE."""

    def test_with_literal(self):
        ax = AnnotationAssertion(
            property=IRI("rdfs:label"),
            subject=IRI(":Dog"),
            value=LangLiteral(value="Dog"),
        )
        entities = _entities(ax)
        assert entities == [
            ("rdfs:label", EntityType.ANNOTATION_PROPERTY, P.PROPERTY),
            (":Dog", None, P.SUBJECT),
        ]

    def test_with_iri_value(self):
        ax = AnnotationAssertion(
            property=IRI("rdfs:seeAlso"),
            subject=IRI(":Dog"),
            value=IRI("ex:DogPage"),
        )
        entities = _entities(ax)
        assert entities == [
            ("rdfs:seeAlso", EntityType.ANNOTATION_PROPERTY, P.PROPERTY),
            (":Dog", None, P.SUBJECT),
            ("ex:DogPage", None, P.VALUE),
        ]


class TestPositionDeclaration:
    """Declaration assigns ENTITY."""

    def test_class_declaration(self):
        ax = Declaration(entity_type=EntityType.CLASS, iri=IRI(":Dog"))
        entities = _entities(ax)
        assert entities == [(":Dog", EntityType.CLASS, P.ENTITY)]

    def test_object_property_declaration(self):
        ax = Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI(":hasPart"))
        entities = _entities(ax)
        assert entities == [(":hasPart", EntityType.OBJECT_PROPERTY, P.ENTITY)]
