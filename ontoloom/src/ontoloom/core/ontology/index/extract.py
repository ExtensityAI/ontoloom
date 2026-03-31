"""Extract (IRI, Role | None) pairs from axioms and class expressions."""

from __future__ import annotations

from collections.abc import Iterator

from ontoloom.core.ontology.index.models import Role
from ontoloom.core.ontology.models.assertions import (
    ClassAssertion,
    DataPropertyAssertion,
    DifferentIndividuals,
    NegativeDataPropertyAssertion,
    NegativeObjectPropertyAssertion,
    ObjectPropertyAssertion,
    SameIndividual,
)
from ontoloom.core.ontology.models.axioms import (
    AnnotationAssertion,
    Axiom,
    DataPropertyDomain,
    DataPropertyRange,
    DisjointClasses,
    EquivalentClasses,
    EquivalentDataProperties,
    EquivalentObjectProperties,
    FunctionalDataProperty,
    HasKey,
    ObjectPropertyDomain,
    ObjectPropertyRange,
    ReflexiveObjectProperty,
    SubClassOf,
    SubDataPropertyOf,
    SubObjectPropertyOf,
    SubObjectPropertyOfChain,
    TransitiveObjectProperty,
)
from ontoloom.core.ontology.models.expressions import (
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
from ontoloom.core.ontology.models.literals import IRI

type Extraction = tuple[IRI, Role | None]


def extract_from_expression(expr: ClassExpression) -> Iterator[Extraction]:
    match expr:
        case NamedClass(iri=iri):
            yield iri, Role.CLASS
        case ObjectSomeValuesFrom(property=prop, filler=filler):
            yield prop, Role.OBJECT_PROPERTY
            yield from extract_from_expression(filler)
        case ObjectIntersectionOf(operands=operands):
            for operand in operands:
                yield from extract_from_expression(operand)
        case ObjectOneOf(individual=ind):
            yield ind, Role.INDIVIDUAL
        case ObjectHasValue(property=prop, individual=ind):
            yield prop, Role.OBJECT_PROPERTY
            yield ind, Role.INDIVIDUAL
        case ObjectHasSelf(property=prop):
            yield prop, Role.OBJECT_PROPERTY
        case DataSomeValuesFrom(property=prop):
            yield prop, Role.DATA_PROPERTY
        case DataHasValue(property=prop):
            yield prop, Role.DATA_PROPERTY


def extract_from_axiom(axiom: Axiom) -> Iterator[Extraction]:  # noqa: C901
    match axiom:
        # TBox
        case SubClassOf(sub_class=sub, super_class=sup):
            yield from extract_from_expression(sub)
            yield from extract_from_expression(sup)
        case EquivalentClasses(expressions=exprs) | DisjointClasses(expressions=exprs):
            for e in exprs:
                yield from extract_from_expression(e)

        # RBox — Object properties
        case SubObjectPropertyOf(sub_property=sub, super_property=sup):
            yield sub, Role.OBJECT_PROPERTY
            yield sup, Role.OBJECT_PROPERTY
        case SubObjectPropertyOfChain(chain=chain, super_property=sup):
            for p in chain:
                yield p, Role.OBJECT_PROPERTY
            yield sup, Role.OBJECT_PROPERTY
        case EquivalentObjectProperties(properties=props):
            for p in props:
                yield p, Role.OBJECT_PROPERTY
        case TransitiveObjectProperty(property=p) | ReflexiveObjectProperty(property=p):
            yield p, Role.OBJECT_PROPERTY
        case ObjectPropertyDomain(property=p, domain=d):
            yield p, Role.OBJECT_PROPERTY
            yield from extract_from_expression(d)
        case ObjectPropertyRange(property=p, range=r):
            yield p, Role.OBJECT_PROPERTY
            yield from extract_from_expression(r)

        # RBox — Data properties
        case SubDataPropertyOf(sub_property=sub, super_property=sup):
            yield sub, Role.DATA_PROPERTY
            yield sup, Role.DATA_PROPERTY
        case EquivalentDataProperties(properties=props):
            for p in props:
                yield p, Role.DATA_PROPERTY
        case DataPropertyDomain(property=p, domain=d):
            yield p, Role.DATA_PROPERTY
            yield from extract_from_expression(d)
        case DataPropertyRange(property=p):
            yield p, Role.DATA_PROPERTY
        case FunctionalDataProperty(property=p):
            yield p, Role.DATA_PROPERTY

        # Other
        case HasKey(class_expression=ce, object_properties=ops, data_properties=dps):
            yield from extract_from_expression(ce)
            for p in ops:
                yield p, Role.OBJECT_PROPERTY
            for p in dps:
                yield p, Role.DATA_PROPERTY
        case AnnotationAssertion(property=p, subject=s):
            yield p, Role.ANNOTATION_PROPERTY
            yield s, None

        # ABox
        case ClassAssertion(class_expression=ce, individual=ind):
            yield from extract_from_expression(ce)
            yield ind, Role.INDIVIDUAL
        case (
            ObjectPropertyAssertion(property=p, source=s, target=t)
            | NegativeObjectPropertyAssertion(property=p, source=s, target=t)
        ):
            yield p, Role.OBJECT_PROPERTY
            yield s, Role.INDIVIDUAL
            yield t, Role.INDIVIDUAL

        case (
            DataPropertyAssertion(property=p, individual=ind)
            | NegativeDataPropertyAssertion(property=p, individual=ind)
        ):
            yield p, Role.DATA_PROPERTY
            yield ind, Role.INDIVIDUAL

        case SameIndividual(individuals=inds) | DifferentIndividuals(individuals=inds):
            for ind in inds:
                yield ind, Role.INDIVIDUAL
