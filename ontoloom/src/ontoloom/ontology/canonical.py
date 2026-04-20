"""Canonical normalization and content hashing for OWL 2 axioms.

OWL 2 treats certain axiom fields as unordered sets (e.g. EquivalentClasses,
DisjointClasses). Without normalization, logically identical axioms would
produce different hashes, creating silent duplicates in the store.
"""

import hashlib
import json

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
from ontoloom.ontology.models.literals import (
    DataIntersectionOf,
    DataOneOf,
    DataRange,
    DataType,
    FrozenModel,
)

_PASSTHROUGH_TYPES = (
    AnnotationAssertion,
    Declaration,
    SubObjectPropertyOf,
    SubObjectPropertyOfChain,
    TransitiveObjectProperty,
    ReflexiveObjectProperty,
    SubDataPropertyOf,
    FunctionalDataProperty,
    SubAnnotationPropertyOf,
    AnnotationPropertyDomain,
    AnnotationPropertyRange,
    ObjectPropertyAssertion,
    NegativeObjectPropertyAssertion,
    DataPropertyAssertion,
    NegativeDataPropertyAssertion,
)


def _to_sort_key(value: FrozenModel | DataType):
    if isinstance(value, str):  # DataType is a StrEnum (str subclass)
        return value
    return json.dumps(value.model_dump(), sort_keys=True, separators=(",", ":"))


def _sort_tuple(values: tuple[str, ...]):
    return tuple(sorted(values))


def _normalize_expressions(exprs: tuple[ClassExpression, ...]):
    normalized = tuple(_normalize_expression(e) for e in exprs)
    return tuple(sorted(normalized, key=_to_sort_key))


def _normalize_data_range(dr: DataRange):
    match dr:
        case DataType() | DataOneOf():
            return dr
        case DataIntersectionOf(operands=operands):
            normalized = [_normalize_data_range(o) for o in operands]
            sorted_operands = tuple(sorted(normalized, key=_to_sort_key))
            return dr.model_copy(update={"operands": sorted_operands})
        case _:
            msg = f"Unhandled DataRange type: {type(dr).__name__}"
            raise ValueError(msg)


def _normalize_expression(expr: ClassExpression):
    match expr:
        case NamedClass() | ObjectOneOf() | ObjectHasValue() | ObjectHasSelf() | DataHasValue():
            return expr
        case ObjectSomeValuesFrom(filler=filler):
            return expr.model_copy(update={"filler": _normalize_expression(filler)})
        case DataSomeValuesFrom(range=r):
            return expr.model_copy(update={"range": _normalize_data_range(r)})
        case ObjectIntersectionOf(operands=operands):
            return expr.model_copy(update={"operands": _normalize_expressions(operands)})
        case _:
            msg = f"Unhandled ClassExpression type: {type(expr).__name__}"
            raise ValueError(msg)


def _normalize_axiom(axiom: Axiom):  # noqa: C901
    if isinstance(axiom, _PASSTHROUGH_TYPES):
        return axiom

    match axiom:
        # Set-semantic IRI tuples
        case EquivalentObjectProperties(properties=props):
            return axiom.model_copy(update={"properties": _sort_tuple(props)})
        case EquivalentDataProperties(properties=props):
            return axiom.model_copy(update={"properties": _sort_tuple(props)})
        case SameIndividual(individuals=inds):
            return axiom.model_copy(update={"individuals": _sort_tuple(inds)})
        case DifferentIndividuals(individuals=inds):
            return axiom.model_copy(update={"individuals": _sort_tuple(inds)})

        # Set-semantic class expression tuples
        case EquivalentClasses(expressions=exprs):
            return axiom.model_copy(update={"expressions": _normalize_expressions(exprs)})
        case DisjointClasses(expressions=exprs):
            return axiom.model_copy(update={"expressions": _normalize_expressions(exprs)})
        case HasKey(class_expression=ce, object_properties=ops, data_properties=dps):
            return axiom.model_copy(
                update={
                    "class_expression": _normalize_expression(ce),
                    "object_properties": _sort_tuple(ops),
                    "data_properties": _sort_tuple(dps),
                }
            )

        # Axioms containing class expressions
        case SubClassOf(sub_class=sub, super_class=sup):
            return axiom.model_copy(
                update={
                    "sub_class": _normalize_expression(sub),
                    "super_class": _normalize_expression(sup),
                }
            )
        case ObjectPropertyDomain(domain=d):
            return axiom.model_copy(update={"domain": _normalize_expression(d)})
        case ObjectPropertyRange(range=r):
            return axiom.model_copy(update={"range": _normalize_expression(r)})
        case DataPropertyDomain(domain=d):
            return axiom.model_copy(update={"domain": _normalize_expression(d)})
        case ClassAssertion(class_expression=ce):
            return axiom.model_copy(update={"class_expression": _normalize_expression(ce)})

        # Axioms containing data ranges
        case DataPropertyRange(range=r):
            return axiom.model_copy(update={"range": _normalize_data_range(r)})
        case DatatypeDefinition(data_range=r):
            return axiom.model_copy(update={"data_range": _normalize_data_range(r)})

        case _:
            msg = f"Unhandled Axiom type: {type(axiom).__name__}"
            raise ValueError(msg)


def canonical_json(axiom: Axiom):
    """Deterministic JSON of an axiom's logical content, excluding annotations."""
    normalized = _normalize_axiom(axiom)
    data = normalized.model_dump(exclude={"annotations"})
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def axiom_hash(axiom: Axiom):
    """SHA-256 of the canonical JSON. Stable across annotation changes and operand reordering."""
    return hashlib.sha256(canonical_json(axiom).encode()).hexdigest()
