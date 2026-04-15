"""Entity extraction from OWL 2 axioms.

Walks axiom and expression structures to yield all referenced entities
with their roles (Class, ObjectProperty, etc.).
"""

from collections.abc import Iterator

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
    Axiom,
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
    ClassExpression,
    DataHasValue,
    DataSomeValuesFrom,
    NamedClass,
    ObjectHasSelf,
    ObjectHasValue,
    ObjectIntersectionOf,
    ObjectOneOf,
    ObjectSomeValuesFrom,
)
from ontoloom.ontology.models.literals import IRI

type EntityRef = tuple[IRI, EntityType | None]


def _iter_expression_entities(expr: ClassExpression) -> Iterator[EntityRef]:
    """Yield all entities referenced in a class expression."""
    match expr:
        case NamedClass(iri=iri):
            yield iri, EntityType.CLASS
        case ObjectSomeValuesFrom(property=prop, filler=filler):
            yield prop, EntityType.OBJECT_PROPERTY
            yield from _iter_expression_entities(filler)
        case ObjectIntersectionOf(operands=operands):
            for operand in operands:
                yield from _iter_expression_entities(operand)
        case ObjectOneOf(individual=ind):
            yield ind, EntityType.NAMED_INDIVIDUAL
        case ObjectHasValue(property=prop, individual=ind):
            yield prop, EntityType.OBJECT_PROPERTY
            yield ind, EntityType.NAMED_INDIVIDUAL
        case ObjectHasSelf(property=prop):
            yield prop, EntityType.OBJECT_PROPERTY
        case DataSomeValuesFrom(property=prop):
            yield prop, EntityType.DATA_PROPERTY
        case DataHasValue(property=prop):
            yield prop, EntityType.DATA_PROPERTY
        case _:
            msg = f"Unhandled ClassExpression type: {type(expr).__name__}"
            raise ValueError(msg)


def iter_axiom_entities(axiom: Axiom) -> Iterator[EntityRef]:  # noqa: C901
    """Yield all entities referenced in an axiom, with their roles."""
    match axiom:
        # TBox
        case SubClassOf(sub_class=sub, super_class=sup):
            yield from _iter_expression_entities(sub)
            yield from _iter_expression_entities(sup)
        case EquivalentClasses(expressions=exprs) | DisjointClasses(expressions=exprs):
            for e in exprs:
                yield from _iter_expression_entities(e)

        # RBox — Object properties
        case SubObjectPropertyOf(sub_property=sub, super_property=sup):
            yield sub, EntityType.OBJECT_PROPERTY
            yield sup, EntityType.OBJECT_PROPERTY
        case SubObjectPropertyOfChain(chain=chain, super_property=sup):
            for p in chain:
                yield p, EntityType.OBJECT_PROPERTY
            yield sup, EntityType.OBJECT_PROPERTY
        case EquivalentObjectProperties(properties=props):
            for p in props:
                yield p, EntityType.OBJECT_PROPERTY
        case TransitiveObjectProperty(property=p) | ReflexiveObjectProperty(property=p):
            yield p, EntityType.OBJECT_PROPERTY
        case ObjectPropertyDomain(property=p, domain=d):
            yield p, EntityType.OBJECT_PROPERTY
            yield from _iter_expression_entities(d)
        case ObjectPropertyRange(property=p, range=r):
            yield p, EntityType.OBJECT_PROPERTY
            yield from _iter_expression_entities(r)

        # RBox — Data properties
        case SubDataPropertyOf(sub_property=sub, super_property=sup):
            yield sub, EntityType.DATA_PROPERTY
            yield sup, EntityType.DATA_PROPERTY
        case EquivalentDataProperties(properties=props):
            for p in props:
                yield p, EntityType.DATA_PROPERTY
        case DataPropertyDomain(property=p, domain=d):
            yield p, EntityType.DATA_PROPERTY
            yield from _iter_expression_entities(d)
        case DataPropertyRange(property=p):
            yield p, EntityType.DATA_PROPERTY
        case FunctionalDataProperty(property=p):
            yield p, EntityType.DATA_PROPERTY

        # Other
        case HasKey(class_expression=ce, object_properties=ops, data_properties=dps):
            yield from _iter_expression_entities(ce)
            for p in ops:
                yield p, EntityType.OBJECT_PROPERTY
            for p in dps:
                yield p, EntityType.DATA_PROPERTY
        case AnnotationAssertion(property=p, subject=s):
            yield p, EntityType.ANNOTATION_PROPERTY
            yield s, None

        # Annotation property axioms
        case SubAnnotationPropertyOf(sub_property=sub, super_property=sup):
            yield sub, EntityType.ANNOTATION_PROPERTY
            yield sup, EntityType.ANNOTATION_PROPERTY
        case AnnotationPropertyDomain(property=p):
            yield p, EntityType.ANNOTATION_PROPERTY
        case AnnotationPropertyRange(property=p):
            yield p, EntityType.ANNOTATION_PROPERTY

        # Datatype and Declaration
        case DatatypeDefinition(datatype=dt):
            yield dt, EntityType.DATATYPE
        case Declaration(entity_type=et, iri=iri):
            yield iri, et

        # ABox
        case ClassAssertion(class_expression=ce, individual=ind):
            yield from _iter_expression_entities(ce)
            yield ind, EntityType.NAMED_INDIVIDUAL
        case (
            ObjectPropertyAssertion(property=p, source=s, target=t)
            | NegativeObjectPropertyAssertion(property=p, source=s, target=t)
        ):
            yield p, EntityType.OBJECT_PROPERTY
            yield s, EntityType.NAMED_INDIVIDUAL
            yield t, EntityType.NAMED_INDIVIDUAL

        case (
            DataPropertyAssertion(property=p, individual=ind)
            | NegativeDataPropertyAssertion(property=p, individual=ind)
        ):
            yield p, EntityType.DATA_PROPERTY
            yield ind, EntityType.NAMED_INDIVIDUAL

        case SameIndividual(individuals=inds) | DifferentIndividuals(individuals=inds):
            for ind in inds:
                yield ind, EntityType.NAMED_INDIVIDUAL

        case _:
            msg = f"Unhandled axiom type in iter_axiom_entities: {type(axiom).__name__}"
            raise ValueError(msg)
