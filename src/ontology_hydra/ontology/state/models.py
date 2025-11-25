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
    parent: "ClassName | None"

    description: str


class DataProperty(Model):
    name: PropertyName
    domain: vartuple[ClassName]
    range: PrimitiveDataType
    description: str


class ObjectProperty(Model):
    name: PropertyName
    domain: vartuple[ClassName]
    range: vartuple[ClassName]
    description: str


Property = ObjectProperty | DataProperty


class OntologyState(Model):
    classes: vartuple[Class]
    data_properties: vartuple[DataProperty]
    object_properties: vartuple[ObjectProperty]

    @property
    def properties(self) -> vartuple[Property]:
        return self.data_properties + self.object_properties

    def get_class(self, name: ClassName):
        return next((cls for cls in self.classes if cls.name == name), None)

    def get_data_property(self, name: PropertyName):
        return next((prop for prop in self.data_properties if prop.name == name), None)

    def get_object_property(self, name: PropertyName):
        return next((prop for prop in self.object_properties if prop.name == name), None)

    def get_property(self, name: PropertyName):
        return next((prop for prop in self.properties if prop.name == name), None)

    def get_subclasses(self, parent_name: ClassName):
        return tuple(cls for cls in self.classes if cls.parent == parent_name)


THING_CLASS = Class(
    name="Thing",
    parent=None,
    description="The root class of all things.",
)

DISPLAY_NAME_PROPERTY = DataProperty(
    name="displayName",
    domain=("Thing",),
    range="string",
    description="A human-readable name for the entity.",
)

DEFAULT_ONTOLOGY_STATE = OntologyState(
    classes=(THING_CLASS,),
    data_properties=(DISPLAY_NAME_PROPERTY,),
    object_properties=(),
)
