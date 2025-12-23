from enum import StrEnum
from typing import NewType

from pydantic import Field

from ontology_hydra.utils.schema import Model

# define custom types for names to enhance static type checking
ClassName = NewType("ClassName", str)
PropertyName = NewType("PropertyName", str)


def is_none(v):
    return v is None


class Description(Model):
    description: str | None = Field(
        None, description="Short human-readable definition for the term.", exclude_if=is_none
    )
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


class IntersectionOf(Model):
    intersectionOf: list[ClassName] = Field(
        ..., description="A class expression defined as an intersection of classes."
    )


ClassExpression = ClassName | IntersectionOf


class Class(Model):
    name: ClassName = Field(..., description="Unique class identifier (PascalCase).")
    description: Description | None = Field(
        None,
        description="Definition and constraints for the class.",
        exclude_if=lambda v: is_none(v) or (v.description is None and v.constraints is None),
    )
    subClassOf: list[ClassName] = Field(
        default_factory=list,
        description="Superclasses for rdfs:subClassOf (supports multiple inheritance).",
    )
    equivalentClass: list[ClassExpression] = Field(
        default_factory=list,
        description="Class expressions equivalent to this class (owl:equivalentClass).",
    )


class DataProperty(Model):
    name: PropertyName = Field(..., description="Data property name (camelCase).")
    description: Description | None = Field(
        None, description="Definition and constraints for the data property."
    )
    subPropertyOf: list[PropertyName] = Field(
        default_factory=list, description="Superproperties for rdfs:subPropertyOf."
    )
    domain: list[ClassExpression] = Field(
        default_factory=list,
        description="Domain classes or intersections (rdfs:domain).",
    )
    range: DataType = Field(..., description="Literal datatype range (rdfs:range).")


class ObjectProperty(Model):
    name: PropertyName = Field(..., description="Object property name (camelCase).")
    description: Description | None = Field(
        None, description="Definition and constraints for the object property."
    )
    subPropertyOf: list[PropertyName] = Field(
        default_factory=list, description="Superproperties for rdfs:subPropertyOf."
    )
    domain: list[ClassExpression] = Field(
        default_factory=list,
        description="Domain classes or intersections (rdfs:domain).",
    )
    range: list[ClassExpression] = Field(
        default_factory=list,
        description="Range classes or intersections (rdfs:range).",
    )
    inverseOf: PropertyName | None = Field(
        None, description="Inverse object property (owl:inverseOf)."
    )


class Ontology(Model):
    classes: dict[ClassName, Class] = Field(
        default_factory=dict, description="Class definitions keyed by class name."
    )
    dataProperties: dict[PropertyName, DataProperty] = Field(
        default_factory=dict, description="Datatype properties keyed by property name."
    )
    objectProperties: dict[PropertyName, ObjectProperty] = Field(
        default_factory=dict, description="Object properties keyed by property name."
    )

    def clone(self):
        # serialize to str and back to get a deep clone. TODO: exchange for something faster
        return Ontology.model_validate_json(self.model_dump_json())

    def get_properties(self, cls: Class):
        class_names = {cls.name}
        queue = list(cls.subClassOf)
        while queue:
            parent = queue.pop()
            if parent in class_names:
                continue
            class_names.add(parent)
            parent_cls = self.classes.get(parent)
            if parent_cls is not None:
                queue.extend(parent_cls.subClassOf)

        def _matches(expr: ClassExpression) -> bool:
            if isinstance(expr, IntersectionOf):
                return all(name in class_names for name in expr.intersectionOf)
            return expr in class_names

        properties: dict[PropertyName, DataProperty | ObjectProperty] = {}
        for name, prop in self.dataProperties.items():
            if any(_matches(expr) for expr in prop.domain):
                properties[name] = prop
        for name, prop in self.objectProperties.items():
            if any(_matches(expr) for expr in prop.domain):
                properties[name] = prop
        return properties


_THING = Class(
    name=ClassName("Thing"),
    description=Description(description="Root class for all entities.", constraints=None),
)
_LABEL = DataProperty(
    name=PropertyName("label"),
    description=Description(description="Human-readable label.", constraints=None),
    domain=[_THING.name],
    range=DataType.STRING,
)

BASE_ONTOLOGY = Ontology(
    classes={_THING.name: _THING},
    dataProperties={_LABEL.name: _LABEL},
    objectProperties={},
)
