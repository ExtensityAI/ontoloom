"""Pattern types: hand-written BasePattern + codegen-emitted subclasses.

The section above the AUTOGEN marker is hand-written. The section below is
regenerated wholesale by `ontoloom.codegen.gen_patterns` from the axiom
hierarchy in `ontoloom.owl.axioms` — do not edit the body by hand.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Tag

from ontoloom.models import FrozenModel, make_tag_resolver, tagged_union_meta
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import DataRange, LangLiteral, TypedLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.patterns.slot import Slot


class BasePattern(FrozenModel):
    """Common base for axiom and expression pattern classes.

    `cls.axiom_tag()` returns the matched OWL type (the class name minus the
    "Pattern" suffix), e.g. `SubClassOfPattern.axiom_tag() == "SubClassOf"`.
    """

    @classmethod
    def axiom_tag(cls):
        return cls.__name__.removesuffix("Pattern")


# ---- AUTOGEN BELOW: do not edit; regenerate via `uv run ontoloom-gen-patterns` ----


class ContainsExpr(FrozenModel):
    """Partial-set match for expression-tuple fields."""

    contains: tuple[ExprSlot, ...]


class ContainsSlot(FrozenModel):
    """Partial-set match for slot-tuple fields (e.g. property lists)."""

    contains: tuple[Slot, ...]


class ObjectSomeValuesFromPattern(BasePattern):
    property: Slot
    filler: ExprSlot


class ObjectIntersectionOfPattern(BasePattern):
    operands: tuple[ExprSlot, ...] | ContainsExpr


class ObjectOneOfPattern(BasePattern):
    individual: Slot


class ObjectHasValuePattern(BasePattern):
    property: Slot
    individual: Slot


class ObjectHasSelfPattern(BasePattern):
    self_property: Slot


class DataSomeValuesFromPattern(BasePattern):
    property: Slot
    range: DataRange | Slot


class DataHasValuePattern(BasePattern):
    property: Slot
    value: TypedLiteral | LangLiteral | Slot


ExprSlot = (
    Slot
    | ObjectSomeValuesFromPattern
    | ObjectIntersectionOfPattern
    | ObjectOneOfPattern
    | ObjectHasValuePattern
    | ObjectHasSelfPattern
    | DataSomeValuesFromPattern
    | DataHasValuePattern
)


class AnnotationAssertionPattern(BasePattern):
    property: Slot
    subject: Slot
    value: IRI | TypedLiteral | LangLiteral | Slot


class SubClassOfPattern(BasePattern):
    sub_class: ExprSlot
    super_class: ExprSlot


class EquivalentClassesPattern(BasePattern):
    equivalent_classes: tuple[ExprSlot, ...] | ContainsExpr


class DisjointClassesPattern(BasePattern):
    disjoint_classes: tuple[ExprSlot, ...] | ContainsExpr


class SubObjectPropertyOfPattern(BasePattern):
    sub_object_property: Slot
    super_object_property: Slot


class SubObjectPropertyOfChainPattern(BasePattern):
    chain: tuple[Slot, ...]
    super_property: Slot


class EquivalentObjectPropertiesPattern(BasePattern):
    object_properties: tuple[Slot, ...] | ContainsSlot


class TransitiveObjectPropertyPattern(BasePattern):
    transitive_property: Slot


class ReflexiveObjectPropertyPattern(BasePattern):
    reflexive_property: Slot


class ObjectPropertyDomainPattern(BasePattern):
    object_property: Slot
    domain: ExprSlot


class ObjectPropertyRangePattern(BasePattern):
    object_property: Slot
    range: ExprSlot


class SubDataPropertyOfPattern(BasePattern):
    sub_data_property: Slot
    super_data_property: Slot


class EquivalentDataPropertiesPattern(BasePattern):
    data_properties: tuple[Slot, ...] | ContainsSlot


class DataPropertyDomainPattern(BasePattern):
    data_property: Slot
    domain: ExprSlot


class DataPropertyRangePattern(BasePattern):
    data_property: Slot
    range: DataRange | Slot


class FunctionalDataPropertyPattern(BasePattern):
    functional_property: Slot


class SubAnnotationPropertyOfPattern(BasePattern):
    sub_annotation_property: Slot
    super_annotation_property: Slot


class AnnotationPropertyDomainPattern(BasePattern):
    annotation_property: Slot
    domain: Slot


class AnnotationPropertyRangePattern(BasePattern):
    annotation_property: Slot
    range: Slot


class HasKeyPattern(BasePattern):
    class_expression: ExprSlot
    object_properties: tuple[Slot, ...] | ContainsSlot
    data_properties: tuple[Slot, ...] | ContainsSlot


class DatatypeDefinitionPattern(BasePattern):
    datatype: Slot
    data_range: DataRange | Slot


class DeclarationPattern(BasePattern):
    entity_type: EntityType | Slot
    iri: Slot


class ClassAssertionPattern(BasePattern):
    class_expression: ExprSlot
    individual: Slot


class ObjectPropertyAssertionPattern(BasePattern):
    property: Slot
    source: Slot
    target: Slot


class NegativeObjectPropertyAssertionPattern(BasePattern):
    property: Slot
    source: Slot
    target: Slot


class DataPropertyAssertionPattern(BasePattern):
    property: Slot
    individual: Slot
    value: TypedLiteral | LangLiteral | Slot


class NegativeDataPropertyAssertionPattern(BasePattern):
    property: Slot
    individual: Slot
    value: TypedLiteral | LangLiteral | Slot


class SameIndividualPattern(BasePattern):
    same_individuals: tuple[Slot, ...] | ContainsSlot


class DifferentIndividualsPattern(BasePattern):
    different_individuals: tuple[Slot, ...] | ContainsSlot


ExpressionPattern = (
    ObjectSomeValuesFromPattern
    | ObjectIntersectionOfPattern
    | ObjectOneOfPattern
    | ObjectHasValuePattern
    | ObjectHasSelfPattern
    | DataSomeValuesFromPattern
    | DataHasValuePattern
)
AxiomPattern = (
    AnnotationAssertionPattern
    | SubClassOfPattern
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
    | SubAnnotationPropertyOfPattern
    | AnnotationPropertyDomainPattern
    | AnnotationPropertyRangePattern
    | HasKeyPattern
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
_PATTERN_CLASSES = (
    ObjectSomeValuesFromPattern,
    ObjectIntersectionOfPattern,
    ObjectOneOfPattern,
    ObjectHasValuePattern,
    ObjectHasSelfPattern,
    DataSomeValuesFromPattern,
    DataHasValuePattern,
    AnnotationAssertionPattern,
    SubClassOfPattern,
    EquivalentClassesPattern,
    DisjointClassesPattern,
    SubObjectPropertyOfPattern,
    SubObjectPropertyOfChainPattern,
    EquivalentObjectPropertiesPattern,
    TransitiveObjectPropertyPattern,
    ReflexiveObjectPropertyPattern,
    ObjectPropertyDomainPattern,
    ObjectPropertyRangePattern,
    SubDataPropertyOfPattern,
    EquivalentDataPropertiesPattern,
    DataPropertyDomainPattern,
    DataPropertyRangePattern,
    FunctionalDataPropertyPattern,
    SubAnnotationPropertyOfPattern,
    AnnotationPropertyDomainPattern,
    AnnotationPropertyRangePattern,
    HasKeyPattern,
    DatatypeDefinitionPattern,
    DeclarationPattern,
    ClassAssertionPattern,
    ObjectPropertyAssertionPattern,
    NegativeObjectPropertyAssertionPattern,
    DataPropertyAssertionPattern,
    NegativeDataPropertyAssertionPattern,
    SameIndividualPattern,
    DifferentIndividualsPattern,
)
_get_pattern_tag = make_tag_resolver(_PATTERN_CLASSES, union_name="Pattern")
Pattern = Annotated[
    Annotated[ObjectSomeValuesFromPattern, Tag("ObjectSomeValuesFromPattern")]
    | Annotated[ObjectIntersectionOfPattern, Tag("ObjectIntersectionOfPattern")]
    | Annotated[ObjectOneOfPattern, Tag("ObjectOneOfPattern")]
    | Annotated[ObjectHasValuePattern, Tag("ObjectHasValuePattern")]
    | Annotated[ObjectHasSelfPattern, Tag("ObjectHasSelfPattern")]
    | Annotated[DataSomeValuesFromPattern, Tag("DataSomeValuesFromPattern")]
    | Annotated[DataHasValuePattern, Tag("DataHasValuePattern")]
    | Annotated[AnnotationAssertionPattern, Tag("AnnotationAssertionPattern")]
    | Annotated[SubClassOfPattern, Tag("SubClassOfPattern")]
    | Annotated[EquivalentClassesPattern, Tag("EquivalentClassesPattern")]
    | Annotated[DisjointClassesPattern, Tag("DisjointClassesPattern")]
    | Annotated[SubObjectPropertyOfPattern, Tag("SubObjectPropertyOfPattern")]
    | Annotated[SubObjectPropertyOfChainPattern, Tag("SubObjectPropertyOfChainPattern")]
    | Annotated[EquivalentObjectPropertiesPattern, Tag("EquivalentObjectPropertiesPattern")]
    | Annotated[TransitiveObjectPropertyPattern, Tag("TransitiveObjectPropertyPattern")]
    | Annotated[ReflexiveObjectPropertyPattern, Tag("ReflexiveObjectPropertyPattern")]
    | Annotated[ObjectPropertyDomainPattern, Tag("ObjectPropertyDomainPattern")]
    | Annotated[ObjectPropertyRangePattern, Tag("ObjectPropertyRangePattern")]
    | Annotated[SubDataPropertyOfPattern, Tag("SubDataPropertyOfPattern")]
    | Annotated[EquivalentDataPropertiesPattern, Tag("EquivalentDataPropertiesPattern")]
    | Annotated[DataPropertyDomainPattern, Tag("DataPropertyDomainPattern")]
    | Annotated[DataPropertyRangePattern, Tag("DataPropertyRangePattern")]
    | Annotated[FunctionalDataPropertyPattern, Tag("FunctionalDataPropertyPattern")]
    | Annotated[SubAnnotationPropertyOfPattern, Tag("SubAnnotationPropertyOfPattern")]
    | Annotated[AnnotationPropertyDomainPattern, Tag("AnnotationPropertyDomainPattern")]
    | Annotated[AnnotationPropertyRangePattern, Tag("AnnotationPropertyRangePattern")]
    | Annotated[HasKeyPattern, Tag("HasKeyPattern")]
    | Annotated[DatatypeDefinitionPattern, Tag("DatatypeDefinitionPattern")]
    | Annotated[DeclarationPattern, Tag("DeclarationPattern")]
    | Annotated[ClassAssertionPattern, Tag("ClassAssertionPattern")]
    | Annotated[ObjectPropertyAssertionPattern, Tag("ObjectPropertyAssertionPattern")]
    | Annotated[
        NegativeObjectPropertyAssertionPattern, Tag("NegativeObjectPropertyAssertionPattern")
    ]
    | Annotated[DataPropertyAssertionPattern, Tag("DataPropertyAssertionPattern")]
    | Annotated[NegativeDataPropertyAssertionPattern, Tag("NegativeDataPropertyAssertionPattern")]
    | Annotated[SameIndividualPattern, Tag("SameIndividualPattern")]
    | Annotated[DifferentIndividualsPattern, Tag("DifferentIndividualsPattern")],
    *tagged_union_meta(_get_pattern_tag),
]

ContainsExpr.model_rebuild()
ContainsSlot.model_rebuild()
ObjectSomeValuesFromPattern.model_rebuild()
ObjectIntersectionOfPattern.model_rebuild()
SubClassOfPattern.model_rebuild()
EquivalentClassesPattern.model_rebuild()
DisjointClassesPattern.model_rebuild()
EquivalentObjectPropertiesPattern.model_rebuild()
ObjectPropertyDomainPattern.model_rebuild()
ObjectPropertyRangePattern.model_rebuild()
EquivalentDataPropertiesPattern.model_rebuild()
DataPropertyDomainPattern.model_rebuild()
HasKeyPattern.model_rebuild()
ClassAssertionPattern.model_rebuild()
SameIndividualPattern.model_rebuild()
DifferentIndividualsPattern.model_rebuild()
