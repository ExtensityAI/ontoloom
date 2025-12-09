from typing import Literal

from ontology_hydra.types import Model, vartuple

type ClassName = str
"""Defines the name of a class in the ontology."""

type PropertyName = str
"""Defines the name of a property in the ontology."""

type PrimitiveDataType = Literal[
    "string", "integer", "float", "boolean", "date", "datetime", "time"
]
"""Defines the primitive data types supported in the ontology."""


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
