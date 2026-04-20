"""Direct unit tests for iter_axiom_entities — verify exact IRIs and roles."""

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
from ontoloom.ontology.models.base import EntityType
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
    LangLiteral,
    TypedLiteral,
)

NC = lambda iri: NamedClass(iri=IRI(iri))


def _entities(axiom):
    return [(str(iri), role) for iri, role in iter_axiom_entities(axiom)]


# -- Declarations --


def test_declaration():
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI(":Dog"))
    assert _entities(ax) == [(":Dog", EntityType.CLASS)]


# -- SubClassOf with expressions --


def test_subclassof_named():
    ax = SubClassOf(sub_class=NC(":Dog"), super_class=NC(":Animal"))
    entities = _entities(ax)
    assert (":Dog", EntityType.CLASS) in entities
    assert (":Animal", EntityType.CLASS) in entities


def test_subclassof_with_some_values_from():
    ax = SubClassOf(
        sub_class=NC(":A"),
        super_class=ObjectSomeValuesFrom(property=IRI(":r"), filler=NC(":B")),
    )
    entities = _entities(ax)
    assert (":A", EntityType.CLASS) in entities
    assert (":r", EntityType.OBJECT_PROPERTY) in entities
    assert (":B", EntityType.CLASS) in entities


def test_subclassof_with_intersection():
    ax = SubClassOf(
        sub_class=NC(":A"),
        super_class=ObjectIntersectionOf(operands=(NC(":B"), NC(":C"))),
    )
    entities = _entities(ax)
    assert (":B", EntityType.CLASS) in entities
    assert (":C", EntityType.CLASS) in entities


# -- Expression types --


def test_object_one_of():
    ax = SubClassOf(sub_class=NC(":A"), super_class=ObjectOneOf(individual=IRI(":x")))
    entities = _entities(ax)
    assert (":x", EntityType.NAMED_INDIVIDUAL) in entities


def test_object_has_value():
    ax = SubClassOf(
        sub_class=NC(":A"),
        super_class=ObjectHasValue(property=IRI(":r"), individual=IRI(":x")),
    )
    entities = _entities(ax)
    assert (":r", EntityType.OBJECT_PROPERTY) in entities
    assert (":x", EntityType.NAMED_INDIVIDUAL) in entities


def test_object_has_self():
    ax = SubClassOf(sub_class=NC(":A"), super_class=ObjectHasSelf(property=IRI(":r")))
    entities = _entities(ax)
    assert (":r", EntityType.OBJECT_PROPERTY) in entities


def test_data_some_values_from():
    ax = SubClassOf(
        sub_class=NC(":A"),
        super_class=DataSomeValuesFrom(property=IRI(":dp"), range=DataType.INTEGER),
    )
    entities = _entities(ax)
    assert (":dp", EntityType.DATA_PROPERTY) in entities


# -- Object property axioms --


def test_sub_object_property_of():
    ax = SubObjectPropertyOf(sub_property=IRI(":r"), super_property=IRI(":s"))
    entities = _entities(ax)
    assert (":r", EntityType.OBJECT_PROPERTY) in entities
    assert (":s", EntityType.OBJECT_PROPERTY) in entities


def test_sub_object_property_of_chain():
    ax = SubObjectPropertyOfChain(
        chain=(IRI(":r1"), IRI(":r2")), super_property=IRI(":s")
    )
    entities = _entities(ax)
    assert (":r1", EntityType.OBJECT_PROPERTY) in entities
    assert (":r2", EntityType.OBJECT_PROPERTY) in entities
    assert (":s", EntityType.OBJECT_PROPERTY) in entities


def test_equivalent_object_properties():
    ax = EquivalentObjectProperties(properties=(IRI(":r"), IRI(":s")))
    entities = _entities(ax)
    assert (":r", EntityType.OBJECT_PROPERTY) in entities
    assert (":s", EntityType.OBJECT_PROPERTY) in entities


def test_transitive_object_property():
    ax = TransitiveObjectProperty(property=IRI(":r"))
    assert _entities(ax) == [(":r", EntityType.OBJECT_PROPERTY)]


def test_object_property_domain():
    ax = ObjectPropertyDomain(property=IRI(":r"), domain=NC(":C"))
    entities = _entities(ax)
    assert (":r", EntityType.OBJECT_PROPERTY) in entities
    assert (":C", EntityType.CLASS) in entities


def test_object_property_range():
    ax = ObjectPropertyRange(property=IRI(":r"), range=NC(":C"))
    entities = _entities(ax)
    assert (":r", EntityType.OBJECT_PROPERTY) in entities
    assert (":C", EntityType.CLASS) in entities


# -- Data property axioms --


def test_sub_data_property_of():
    ax = SubDataPropertyOf(sub_property=IRI(":dp1"), super_property=IRI(":dp2"))
    entities = _entities(ax)
    assert (":dp1", EntityType.DATA_PROPERTY) in entities
    assert (":dp2", EntityType.DATA_PROPERTY) in entities


def test_data_property_domain():
    ax = DataPropertyDomain(property=IRI(":dp"), domain=NC(":C"))
    entities = _entities(ax)
    assert (":dp", EntityType.DATA_PROPERTY) in entities
    assert (":C", EntityType.CLASS) in entities


def test_data_property_range():
    ax = DataPropertyRange(property=IRI(":dp"), range=DataType.INTEGER)
    entities = _entities(ax)
    assert (":dp", EntityType.DATA_PROPERTY) in entities


def test_functional_data_property():
    ax = FunctionalDataProperty(property=IRI(":dp"))
    assert _entities(ax) == [(":dp", EntityType.DATA_PROPERTY)]


def test_has_key():
    ax = HasKey(
        class_expression=NC(":C"),
        object_properties=(IRI(":op"),),
        data_properties=(IRI(":dp"),),
    )
    entities = _entities(ax)
    assert (":C", EntityType.CLASS) in entities
    assert (":op", EntityType.OBJECT_PROPERTY) in entities
    assert (":dp", EntityType.DATA_PROPERTY) in entities


# -- Annotation axioms --


def test_annotation_assertion_with_lang_literal():
    ax = AnnotationAssertion(
        property=IRI("rdfs:label"), subject=IRI(":Dog"), value=LangLiteral(value="Dog")
    )
    entities = _entities(ax)
    assert ("rdfs:label", EntityType.ANNOTATION_PROPERTY) in entities
    assert (":Dog", None) in entities


def test_annotation_assertion_with_iri_value():
    ax = AnnotationAssertion(
        property=IRI("rdfs:seeAlso"), subject=IRI(":Dog"), value=IRI("ex:DogPage")
    )
    entities = _entities(ax)
    assert ("rdfs:seeAlso", EntityType.ANNOTATION_PROPERTY) in entities
    assert (":Dog", None) in entities
    assert ("ex:DogPage", None) in entities


def test_sub_annotation_property_of():
    ax = SubAnnotationPropertyOf(
        sub_property=IRI("skos:definition"), super_property=IRI("rdfs:comment")
    )
    entities = _entities(ax)
    assert ("skos:definition", EntityType.ANNOTATION_PROPERTY) in entities
    assert ("rdfs:comment", EntityType.ANNOTATION_PROPERTY) in entities


def test_annotation_property_domain():
    ax = AnnotationPropertyDomain(property=IRI("rdfs:label"), domain=IRI("owl:Thing"))
    entities = _entities(ax)
    assert ("rdfs:label", EntityType.ANNOTATION_PROPERTY) in entities
    assert ("owl:Thing", None) in entities


def test_annotation_property_range():
    ax = AnnotationPropertyRange(property=IRI("rdfs:label"), range=IRI("rdfs:Literal"))
    entities = _entities(ax)
    assert ("rdfs:label", EntityType.ANNOTATION_PROPERTY) in entities
    assert ("rdfs:Literal", None) in entities


# -- ABox assertions --


def test_class_assertion():
    ax = ClassAssertion(class_expression=NC(":Dog"), individual=IRI(":Fido"))
    entities = _entities(ax)
    assert (":Dog", EntityType.CLASS) in entities
    assert (":Fido", EntityType.NAMED_INDIVIDUAL) in entities


def test_object_property_assertion():
    ax = ObjectPropertyAssertion(property=IRI(":owns"), source=IRI(":Alice"), target=IRI(":Fido"))
    entities = _entities(ax)
    assert (":owns", EntityType.OBJECT_PROPERTY) in entities
    assert (":Alice", EntityType.NAMED_INDIVIDUAL) in entities
    assert (":Fido", EntityType.NAMED_INDIVIDUAL) in entities


def test_negative_object_property_assertion():
    ax = NegativeObjectPropertyAssertion(
        property=IRI(":owns"), source=IRI(":Alice"), target=IRI(":Rex")
    )
    entities = _entities(ax)
    assert (":owns", EntityType.OBJECT_PROPERTY) in entities
    assert (":Alice", EntityType.NAMED_INDIVIDUAL) in entities
    assert (":Rex", EntityType.NAMED_INDIVIDUAL) in entities


def test_data_property_assertion():
    ax = DataPropertyAssertion(
        property=IRI(":hasAge"),
        individual=IRI(":Alice"),
        value=TypedLiteral(value="30", datatype=DataType.INTEGER),
    )
    entities = _entities(ax)
    assert (":hasAge", EntityType.DATA_PROPERTY) in entities
    assert (":Alice", EntityType.NAMED_INDIVIDUAL) in entities


def test_same_individual():
    ax = SameIndividual(individuals=(IRI(":Bob"), IRI(":Robert")))
    entities = _entities(ax)
    assert (":Bob", EntityType.NAMED_INDIVIDUAL) in entities
    assert (":Robert", EntityType.NAMED_INDIVIDUAL) in entities


def test_different_individuals():
    ax = DifferentIndividuals(individuals=(IRI(":Alice"), IRI(":Bob")))
    entities = _entities(ax)
    assert (":Alice", EntityType.NAMED_INDIVIDUAL) in entities
    assert (":Bob", EntityType.NAMED_INDIVIDUAL) in entities


# -- Axiom-level annotations --


def test_axiom_level_annotation_property_extracted():
    ax = SubClassOf(
        sub_class=NC(":Dog"),
        super_class=NC(":Animal"),
        annotations=(
            Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note")),
        ),
    )
    entities = _entities(ax)
    assert ("rdfs:comment", EntityType.ANNOTATION_PROPERTY) in entities


def test_axiom_level_annotation_iri_value_extracted():
    ax = SubClassOf(
        sub_class=NC(":Dog"),
        super_class=NC(":Animal"),
        annotations=(
            Annotation(property=IRI("rdfs:seeAlso"), value=IRI("ex:Reference")),
        ),
    )
    entities = _entities(ax)
    assert ("rdfs:seeAlso", EntityType.ANNOTATION_PROPERTY) in entities
    assert ("ex:Reference", None) in entities


# -- Set-semantic axioms --


def test_equivalent_classes():
    ax = EquivalentClasses(expressions=(NC(":A"), NC(":B")))
    entities = _entities(ax)
    assert (":A", EntityType.CLASS) in entities
    assert (":B", EntityType.CLASS) in entities


def test_disjoint_classes():
    ax = DisjointClasses(expressions=(NC(":A"), NC(":B")))
    entities = _entities(ax)
    assert (":A", EntityType.CLASS) in entities
    assert (":B", EntityType.CLASS) in entities
