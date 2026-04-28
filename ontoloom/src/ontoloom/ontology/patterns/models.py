"""Pattern models for structural axiom search.

A pattern mirrors the axiom/expression class hierarchy with Slot-typed fields.
Slot is a str subclass: "ex:Dog" (concrete IRI), "?C" (variable), "*" (wildcard).

Expression-level patterns (outermost type is an expression) match substructures
within any axiom at any depth.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ontoloom.ontology.models.base import EntityType
from ontoloom.ontology.models.literals import (
    IRI,
    DataRange,
    FrozenModel,
    LangLiteral,
    TypedLiteral,
)

# ---------------------------------------------------------------------------
# Slot: the universal pattern primitive
# ---------------------------------------------------------------------------

_IRI_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_.-]*)?:[^\x00-\x1f]+$")
_VAR_RE = re.compile(r"^\?[a-zA-Z_][a-zA-Z0-9_]*$")


class Slot(str):
    """A pattern slot: concrete IRI, variable (?name), or wildcard (*).

    - "ex:Dog"  → concrete IRI (validated)
    - "?C"      → variable (binds to matched value)
    - "*"       → wildcard (matches anything, no binding)
    """

    def __new__(cls, value: str):
        if value == "*":
            pass
        elif value.startswith("?"):
            if not _VAR_RE.match(value):
                msg = f"Variable must be ?identifier, got {value!r}"
                raise ValueError(msg)
        else:
            if not _IRI_RE.match(value):
                msg = f"Slot must be IRI (prefix:name), ?variable, or *, got {value!r}"
                raise ValueError(msg)
        return str.__new__(cls, value)

    @property
    def is_wildcard(self) -> bool:
        return self == "*"

    @property
    def is_variable(self) -> bool:
        return self.startswith("?")

    @property
    def is_iri(self) -> bool:
        return not self.is_wildcard and not self.is_variable

    @property
    def var_name(self) -> str:
        return self[1:]

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: Any, handler: Any) -> dict[str, Any]:
        return {
            "type": "string",
            "description": 'IRI ("prefix:name"), variable ("?name"), or wildcard ("*")',
            "examples": ["ex:Dog", "?C", "*"],
        }


# ---------------------------------------------------------------------------
# Contains: partial list matching
# ---------------------------------------------------------------------------


class ContainsExpr(FrozenModel):
    """Partial match for expression list fields (e.g., ObjectIntersectionOf.operands).
    The actual list must include at least these items, in any order."""

    contains: tuple[ExprSlot, ...]


class ContainsSlot(FrozenModel):
    """Partial match for IRI list fields (e.g., chain, properties, individuals).
    The actual list must include at least these items, in any order."""

    contains: tuple[Slot, ...]


# ---------------------------------------------------------------------------
# Expression patterns
# ---------------------------------------------------------------------------


class NamedClassPattern(FrozenModel):
    type: Literal["NamedClassPattern"] = "NamedClassPattern"
    iri: Slot


class ObjectSomeValuesFromPattern(FrozenModel):
    type: Literal["ObjectSomeValuesFromPattern"] = "ObjectSomeValuesFromPattern"
    property: Slot
    filler: ExprSlot


class ObjectIntersectionOfPattern(FrozenModel):
    type: Literal["ObjectIntersectionOfPattern"] = "ObjectIntersectionOfPattern"
    operands: tuple[ExprSlot, ...] | ContainsExpr


class ObjectOneOfPattern(FrozenModel):
    type: Literal["ObjectOneOfPattern"] = "ObjectOneOfPattern"
    individual: Slot


class ObjectHasValuePattern(FrozenModel):
    type: Literal["ObjectHasValuePattern"] = "ObjectHasValuePattern"
    property: Slot
    individual: Slot


class ObjectHasSelfPattern(FrozenModel):
    type: Literal["ObjectHasSelfPattern"] = "ObjectHasSelfPattern"
    property: Slot


class DataSomeValuesFromPattern(FrozenModel):
    type: Literal["DataSomeValuesFromPattern"] = "DataSomeValuesFromPattern"
    property: Slot
    range: DataRange | Slot


class DataHasValuePattern(FrozenModel):
    type: Literal["DataHasValuePattern"] = "DataHasValuePattern"
    property: Slot
    value: TypedLiteral | LangLiteral | Slot


# Expression slot: a Slot (str) or a full expression pattern (dict)
ExprSlot = (
    Slot
    | NamedClassPattern
    | ObjectSomeValuesFromPattern
    | ObjectIntersectionOfPattern
    | ObjectOneOfPattern
    | ObjectHasValuePattern
    | ObjectHasSelfPattern
    | DataSomeValuesFromPattern
    | DataHasValuePattern
)


# ---------------------------------------------------------------------------
# Axiom patterns — TBox
# ---------------------------------------------------------------------------


class SubClassOfPattern(FrozenModel):
    type: Literal["SubClassOfPattern"] = "SubClassOfPattern"
    sub_class: ExprSlot
    super_class: ExprSlot


class EquivalentClassesPattern(FrozenModel):
    type: Literal["EquivalentClassesPattern"] = "EquivalentClassesPattern"
    expressions: tuple[ExprSlot, ...] | ContainsExpr


class DisjointClassesPattern(FrozenModel):
    type: Literal["DisjointClassesPattern"] = "DisjointClassesPattern"
    expressions: tuple[ExprSlot, ...] | ContainsExpr


# ---------------------------------------------------------------------------
# Axiom patterns — RBox (Object Properties)
# ---------------------------------------------------------------------------


class SubObjectPropertyOfPattern(FrozenModel):
    type: Literal["SubObjectPropertyOfPattern"] = "SubObjectPropertyOfPattern"
    sub_property: Slot
    super_property: Slot


class SubObjectPropertyOfChainPattern(FrozenModel):
    type: Literal["SubObjectPropertyOfChainPattern"] = "SubObjectPropertyOfChainPattern"
    chain: tuple[Slot, ...] | ContainsSlot
    super_property: Slot


class EquivalentObjectPropertiesPattern(FrozenModel):
    type: Literal["EquivalentObjectPropertiesPattern"] = "EquivalentObjectPropertiesPattern"
    properties: tuple[Slot, ...] | ContainsSlot


class TransitiveObjectPropertyPattern(FrozenModel):
    type: Literal["TransitiveObjectPropertyPattern"] = "TransitiveObjectPropertyPattern"
    property: Slot


class ReflexiveObjectPropertyPattern(FrozenModel):
    type: Literal["ReflexiveObjectPropertyPattern"] = "ReflexiveObjectPropertyPattern"
    property: Slot


class ObjectPropertyDomainPattern(FrozenModel):
    type: Literal["ObjectPropertyDomainPattern"] = "ObjectPropertyDomainPattern"
    property: Slot
    domain: ExprSlot


class ObjectPropertyRangePattern(FrozenModel):
    type: Literal["ObjectPropertyRangePattern"] = "ObjectPropertyRangePattern"
    property: Slot
    range: ExprSlot


# ---------------------------------------------------------------------------
# Axiom patterns — RBox (Data Properties)
# ---------------------------------------------------------------------------


class SubDataPropertyOfPattern(FrozenModel):
    type: Literal["SubDataPropertyOfPattern"] = "SubDataPropertyOfPattern"
    sub_property: Slot
    super_property: Slot


class EquivalentDataPropertiesPattern(FrozenModel):
    type: Literal["EquivalentDataPropertiesPattern"] = "EquivalentDataPropertiesPattern"
    properties: tuple[Slot, ...] | ContainsSlot


class DataPropertyDomainPattern(FrozenModel):
    type: Literal["DataPropertyDomainPattern"] = "DataPropertyDomainPattern"
    property: Slot
    domain: ExprSlot


class DataPropertyRangePattern(FrozenModel):
    type: Literal["DataPropertyRangePattern"] = "DataPropertyRangePattern"
    property: Slot
    range: DataRange | Slot


class FunctionalDataPropertyPattern(FrozenModel):
    type: Literal["FunctionalDataPropertyPattern"] = "FunctionalDataPropertyPattern"
    property: Slot


# ---------------------------------------------------------------------------
# Axiom patterns — Keys, Annotations, Datatypes, Declarations
# ---------------------------------------------------------------------------


class HasKeyPattern(FrozenModel):
    type: Literal["HasKeyPattern"] = "HasKeyPattern"
    class_expression: ExprSlot
    object_properties: tuple[Slot, ...] | ContainsSlot
    data_properties: tuple[Slot, ...] | ContainsSlot


class AnnotationAssertionPattern(FrozenModel):
    type: Literal["AnnotationAssertionPattern"] = "AnnotationAssertionPattern"
    property: Slot
    subject: Slot
    value: IRI | TypedLiteral | LangLiteral | Slot


class SubAnnotationPropertyOfPattern(FrozenModel):
    type: Literal["SubAnnotationPropertyOfPattern"] = "SubAnnotationPropertyOfPattern"
    sub_property: Slot
    super_property: Slot


class AnnotationPropertyDomainPattern(FrozenModel):
    type: Literal["AnnotationPropertyDomainPattern"] = "AnnotationPropertyDomainPattern"
    property: Slot
    domain: Slot


class AnnotationPropertyRangePattern(FrozenModel):
    type: Literal["AnnotationPropertyRangePattern"] = "AnnotationPropertyRangePattern"
    property: Slot
    range: Slot


class DatatypeDefinitionPattern(FrozenModel):
    type: Literal["DatatypeDefinitionPattern"] = "DatatypeDefinitionPattern"
    datatype: Slot
    data_range: DataRange | Slot


class DeclarationPattern(FrozenModel):
    type: Literal["DeclarationPattern"] = "DeclarationPattern"
    entity_type: EntityType | Slot
    iri: Slot


# ---------------------------------------------------------------------------
# Axiom patterns — ABox (Assertions)
# ---------------------------------------------------------------------------


class ClassAssertionPattern(FrozenModel):
    type: Literal["ClassAssertionPattern"] = "ClassAssertionPattern"
    class_expression: ExprSlot
    individual: Slot


class ObjectPropertyAssertionPattern(FrozenModel):
    type: Literal["ObjectPropertyAssertionPattern"] = "ObjectPropertyAssertionPattern"
    property: Slot
    source: Slot
    target: Slot


class NegativeObjectPropertyAssertionPattern(FrozenModel):
    type: Literal["NegativeObjectPropertyAssertionPattern"] = (
        "NegativeObjectPropertyAssertionPattern"
    )
    property: Slot
    source: Slot
    target: Slot


class DataPropertyAssertionPattern(FrozenModel):
    type: Literal["DataPropertyAssertionPattern"] = "DataPropertyAssertionPattern"
    property: Slot
    individual: Slot
    value: TypedLiteral | LangLiteral | Slot


class NegativeDataPropertyAssertionPattern(FrozenModel):
    type: Literal["NegativeDataPropertyAssertionPattern"] = "NegativeDataPropertyAssertionPattern"
    property: Slot
    individual: Slot
    value: TypedLiteral | LangLiteral | Slot


class SameIndividualPattern(FrozenModel):
    type: Literal["SameIndividualPattern"] = "SameIndividualPattern"
    individuals: tuple[Slot, ...] | ContainsSlot


class DifferentIndividualsPattern(FrozenModel):
    type: Literal["DifferentIndividualsPattern"] = "DifferentIndividualsPattern"
    individuals: tuple[Slot, ...] | ContainsSlot


# ---------------------------------------------------------------------------
# Pattern unions
# ---------------------------------------------------------------------------
# AxiomPattern and ExpressionPattern are plain unions (no Annotated wrapper) so
# `Pattern = AxiomPattern | ExpressionPattern` flattens into one union of all
# subtypes. The single `Annotated[..., Field(discriminator="type")]` at the
# Pattern level then emits one flat `oneOf`+`discriminator` schema — nesting
# Annotated unions emits `anyOf [oneOf, oneOf]`, which LLMs mishandle.

ExpressionPattern = (
    NamedClassPattern
    | ObjectSomeValuesFromPattern
    | ObjectIntersectionOfPattern
    | ObjectOneOfPattern
    | ObjectHasValuePattern
    | ObjectHasSelfPattern
    | DataSomeValuesFromPattern
    | DataHasValuePattern
)

AxiomPattern = (
    SubClassOfPattern
    | EquivalentClassesPattern
    | DisjointClassesPattern
    | SubObjectPropertyOfPattern
    | SubObjectPropertyOfChainPattern
    | EquivalentObjectPropertiesPattern
    | TransitiveObjectPropertyPattern
    | ReflexiveObjectPropertyPattern
    | ObjectPropertyDomainPattern
    | ObjectPropertyRangePattern
    | SubDataPropertyOfPattern
    | EquivalentDataPropertiesPattern
    | DataPropertyDomainPattern
    | DataPropertyRangePattern
    | FunctionalDataPropertyPattern
    | HasKeyPattern
    | AnnotationAssertionPattern
    | SubAnnotationPropertyOfPattern
    | AnnotationPropertyDomainPattern
    | AnnotationPropertyRangePattern
    | DatatypeDefinitionPattern
    | DeclarationPattern
    | ClassAssertionPattern
    | ObjectPropertyAssertionPattern
    | NegativeObjectPropertyAssertionPattern
    | DataPropertyAssertionPattern
    | NegativeDataPropertyAssertionPattern
    | SameIndividualPattern
    | DifferentIndividualsPattern
)

Pattern = Annotated[AxiomPattern | ExpressionPattern, Field(discriminator="type")]

# Rebuild forward refs for recursive types
ObjectSomeValuesFromPattern.model_rebuild()
ObjectIntersectionOfPattern.model_rebuild()
ContainsExpr.model_rebuild()
