from typing import Literal

from pydantic import ConfigDict
from symai.strategy import LLMDataModel

type vartuple[T] = tuple[T, ...]
"""A tuple of variable length containing elements of type T."""

type ClassName = str
type PropertyName = str
type PrimitiveDataType = Literal[
    "string", "integer", "float", "boolean", "date", "datetime", "time"
]


class Model(LLMDataModel):
    model_config = ConfigDict(
        frozen=True,  # immutable by default
        strict=True,  # no extra fields allowed
    )


class Class(Model):
    name: ClassName
    parent: "ClassName | None" = None

    description: str


class ObjectProperty(Model):
    name: PropertyName
    domain: vartuple[ClassName]
    range: vartuple[ClassName]
    description: str


class DataProperty(Model):
    name: PropertyName
    domain: vartuple[ClassName]
    range: PrimitiveDataType
    description: str


Property = ObjectProperty | DataProperty


class OntologyState(Model):
    classes: vartuple[Class]
    properties: vartuple[Property]

    def get_class(self, name: ClassName) -> Class | None:
        return next((cls for cls in self.classes if cls.name == name), None)

    def get_property(self, name: PropertyName) -> Property | None:
        return next((prop for prop in self.properties if prop.name == name), None)


DEFAULT_ONTOLOGY_STATE = OntologyState(
    classes=(Class(name="Thing", description="The root class of all things."),),
    properties=(
        DataProperty(
            name="displayName",
            domain=("Thing",),
            range="string",
            description="A human-readable name for the entity.",
        ),
    ),
)
