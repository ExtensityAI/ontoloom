# note: commented out fields denote future features that are planned but not yet implemented

from enum import StrEnum
from typing import NewType

from pydantic import Field

from ontology_hydra.utils.schema.llm import DataModel

# define custom types for names to enhance static type checking
ClassName = NewType("ClassName", str)
PropertyName = NewType("PropertyName", str)


def is_none(v):
    return v is None


class Description(DataModel):
    definition: str = Field(..., description="Short human-readable definition.")
    constraints: str | None = Field(
        None, description="Optional constraints or modeling notes.", exclude_if=is_none
    )


class DataType(StrEnum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    TIME = "time"


class IntersectionOf(DataModel):
    """An intersection of multiple classes."""

    classes: list[ClassName] = Field(..., description="The list of classes to intersect.")


ClassExpression = ClassName | IntersectionOf


class Class(DataModel):
    name: ClassName = Field(..., description="Unique class identifier (PascalCase).")
    description: Description = Field(
        default=...,
        description="Definition and constraints for the class.",
    )
    sub_class_of: list[ClassName] = Field(
        default_factory=list,
        description="Superclasses for rdfs:subClassOf (supports multiple inheritance).",
    )


#    equivalent_class: list[ClassExpression] = Field(
#        default_factory=list,
#        description="Class expressions equivalent to this class (owl:equivalentClass).",
#    )


class DataProperty(DataModel):
    name: PropertyName = Field(..., description="Data property name (camelCase).")
    description: Description = Field(
        ..., description="Definition and constraints for the data property."
    )
    #    sub_property_of: list[PropertyName] = Field(
    #        default_factory=list, description="Superproperties for rdfs:subPropertyOf."
    #    )
    domain: list[ClassExpression] = Field(
        default_factory=list,
        description="Domain classes or intersections (rdfs:domain).",
    )
    range: DataType = Field(..., description="Literal datatype range (rdfs:range).")


class ObjectProperty(DataModel):
    name: PropertyName = Field(..., description="Object property name (camelCase).")
    description: Description = Field(
        ..., description="Definition and constraints for the object property."
    )
    #    sub_property_of: list[PropertyName] = Field(
    #        default_factory=list, description="Superproperties for rdfs:subPropertyOf."
    #    )
    domain: list[ClassExpression] = Field(
        default_factory=list,
        description="Domain classes or intersections (rdfs:domain).",
    )
    range: list[ClassExpression] = Field(
        default_factory=list,
        description="Range classes or intersections (rdfs:range).",
    )


#    inverse_of: PropertyName | None = Field(
#        None, description="Inverse object property (owl:inverseOf)."
#    )


class Ontology(DataModel):
    classes: dict[ClassName, Class] = Field(
        default_factory=dict, description="Class definitions keyed by class name."
    )
    data_properties: dict[PropertyName, DataProperty] = Field(
        default_factory=dict, description="Datatype properties keyed by property name."
    )
    object_properties: dict[PropertyName, ObjectProperty] = Field(
        default_factory=dict, description="Object properties keyed by property name."
    )

    def clone(self):
        # serialize to str and back to get a deep clone. TODO: exchange for something faster
        return Ontology.model_validate_json(self.model_dump_json())


_THING = Class(
    name=ClassName("Thing"),
    description=Description(definition="Root class for all entities.", constraints=None),
)
_LABEL = DataProperty(
    name=PropertyName("label"),
    description=Description(definition="Human-readable label.", constraints=None),
    domain=[_THING.name],
    range=DataType.STRING,
)

BASE_ONTOLOGY = Ontology(
    classes={_THING.name: _THING},
    data_properties={_LABEL.name: _LABEL},
    object_properties={},
)
