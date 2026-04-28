"""Entity extraction from OWL 2 axioms.

Walks axiom and expression structures to yield all referenced entities
with their roles (Class, ObjectProperty, etc.) and structural positions.
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
from ontoloom.ontology.types import Position

type EntityRef = tuple[IRI, EntityType | None, Position | None]


def _iter_expression_entities(
    expr: ClassExpression,
    parent_position: Position,
) -> Iterator[EntityRef]:
    """Yield all entities referenced in a class expression with positions."""
    match expr:
        case NamedClass(iri=iri):
            yield iri, EntityType.CLASS, parent_position
        case ObjectSomeValuesFrom(property=prop, filler=filler):
            yield prop, EntityType.OBJECT_PROPERTY, Position.RESTRICTION_PROPERTY
            yield from _iter_expression_entities(filler, Position.FILLER)
        case ObjectIntersectionOf(operands=operands):
            for operand in operands:
                yield from _iter_expression_entities(operand, parent_position)
        case ObjectOneOf(individual=ind):
            yield ind, EntityType.NAMED_INDIVIDUAL, parent_position
        case ObjectHasValue(property=prop, individual=ind):
            yield prop, EntityType.OBJECT_PROPERTY, Position.RESTRICTION_PROPERTY
            yield ind, EntityType.NAMED_INDIVIDUAL, Position.FILLER
        case ObjectHasSelf(property=prop):
            yield prop, EntityType.OBJECT_PROPERTY, Position.RESTRICTION_PROPERTY
        case DataSomeValuesFrom(property=prop):
            yield prop, EntityType.DATA_PROPERTY, Position.RESTRICTION_PROPERTY
        case DataHasValue(property=prop):
            yield prop, EntityType.DATA_PROPERTY, Position.RESTRICTION_PROPERTY
        case _:
            msg = f"Unhandled ClassExpression type: {type(expr).__name__}"
            raise ValueError(msg)


def iter_axiom_entities(axiom: Axiom) -> Iterator[EntityRef]:  # noqa: C901
    """Yield all entities referenced in an axiom, with their roles and positions."""
    match axiom:
        # TBox
        case SubClassOf(sub_class=sub, super_class=sup):
            yield from _iter_expression_entities(sub, Position.SUB_CLASS)
            yield from _iter_expression_entities(sup, Position.SUPER_CLASS)
        case EquivalentClasses(expressions=exprs) | DisjointClasses(expressions=exprs):
            for e in exprs:
                yield from _iter_expression_entities(e, Position.MEMBER)

        # RBox — Object properties
        case SubObjectPropertyOf(sub_property=sub, super_property=sup):
            yield sub, EntityType.OBJECT_PROPERTY, Position.SUB_PROPERTY
            yield sup, EntityType.OBJECT_PROPERTY, Position.SUPER_PROPERTY
        case SubObjectPropertyOfChain(chain=chain, super_property=sup):
            for p in chain:
                yield p, EntityType.OBJECT_PROPERTY, Position.CHAIN_MEMBER
            yield sup, EntityType.OBJECT_PROPERTY, Position.SUPER_PROPERTY
        case EquivalentObjectProperties(properties=props):
            for p in props:
                yield p, EntityType.OBJECT_PROPERTY, Position.MEMBER
        case TransitiveObjectProperty(property=p) | ReflexiveObjectProperty(property=p):
            yield p, EntityType.OBJECT_PROPERTY, Position.PROPERTY
        case ObjectPropertyDomain(property=p, domain=d):
            yield p, EntityType.OBJECT_PROPERTY, Position.PROPERTY
            yield from _iter_expression_entities(d, Position.DOMAIN)
        case ObjectPropertyRange(property=p, range=r):
            yield p, EntityType.OBJECT_PROPERTY, Position.PROPERTY
            yield from _iter_expression_entities(r, Position.RANGE)

        # RBox — Data properties
        case SubDataPropertyOf(sub_property=sub, super_property=sup):
            yield sub, EntityType.DATA_PROPERTY, Position.SUB_PROPERTY
            yield sup, EntityType.DATA_PROPERTY, Position.SUPER_PROPERTY
        case EquivalentDataProperties(properties=props):
            for p in props:
                yield p, EntityType.DATA_PROPERTY, Position.MEMBER
        case DataPropertyDomain(property=p, domain=d):
            yield p, EntityType.DATA_PROPERTY, Position.PROPERTY
            yield from _iter_expression_entities(d, Position.DOMAIN)
        case DataPropertyRange(property=p):
            yield p, EntityType.DATA_PROPERTY, Position.PROPERTY
        case FunctionalDataProperty(property=p):
            yield p, EntityType.DATA_PROPERTY, Position.PROPERTY

        # Other
        case HasKey(class_expression=ce, object_properties=ops, data_properties=dps):
            yield from _iter_expression_entities(ce, Position.CLASS)
            for p in ops:
                yield p, EntityType.OBJECT_PROPERTY, Position.PROPERTY
            for p in dps:
                yield p, EntityType.DATA_PROPERTY, Position.PROPERTY
        case AnnotationAssertion(property=p, subject=s, value=v):
            yield p, EntityType.ANNOTATION_PROPERTY, Position.PROPERTY
            yield s, None, Position.SUBJECT
            if isinstance(v, IRI):
                yield v, None, Position.VALUE

        # Annotation property axioms
        case SubAnnotationPropertyOf(sub_property=sub, super_property=sup):
            yield sub, EntityType.ANNOTATION_PROPERTY, Position.SUB_PROPERTY
            yield sup, EntityType.ANNOTATION_PROPERTY, Position.SUPER_PROPERTY
        case AnnotationPropertyDomain(property=p, domain=d):
            yield p, EntityType.ANNOTATION_PROPERTY, Position.PROPERTY
            yield d, None, Position.DOMAIN
        case AnnotationPropertyRange(property=p, range=r):
            yield p, EntityType.ANNOTATION_PROPERTY, Position.PROPERTY
            yield r, None, Position.RANGE

        # Datatype and Declaration
        case DatatypeDefinition(datatype=dt):
            yield dt, EntityType.DATATYPE, Position.ENTITY
        case Declaration(entity_type=et, iri=iri):
            yield iri, et, Position.ENTITY

        # ABox
        case ClassAssertion(class_expression=ce, individual=ind):
            yield from _iter_expression_entities(ce, Position.CLASS)
            yield ind, EntityType.NAMED_INDIVIDUAL, Position.INDIVIDUAL
        case (
            ObjectPropertyAssertion(property=p, source=s, target=t)
            | NegativeObjectPropertyAssertion(property=p, source=s, target=t)
        ):
            yield p, EntityType.OBJECT_PROPERTY, Position.PROPERTY
            yield s, EntityType.NAMED_INDIVIDUAL, Position.SOURCE
            yield t, EntityType.NAMED_INDIVIDUAL, Position.TARGET

        case (
            DataPropertyAssertion(property=p, individual=ind)
            | NegativeDataPropertyAssertion(property=p, individual=ind)
        ):
            yield p, EntityType.DATA_PROPERTY, Position.PROPERTY
            yield ind, EntityType.NAMED_INDIVIDUAL, Position.INDIVIDUAL

        case SameIndividual(individuals=inds) | DifferentIndividuals(individuals=inds):
            for ind in inds:
                yield ind, EntityType.NAMED_INDIVIDUAL, Position.MEMBER

        case _:
            msg = f"Unhandled axiom type in iter_axiom_entities: {type(axiom).__name__}"
            raise ValueError(msg)

    for ann in axiom.annotations:
        yield ann.property, EntityType.ANNOTATION_PROPERTY, Position.PROPERTY
        if isinstance(ann.value, IRI):
            yield ann.value, None, Position.VALUE
