from typing import Literal

from pydantic import ConfigDict, Field
from symai.strategy import LLMDataModel

Characteristic = Literal[
    "functional",
    "inverseFunctional",
    "transitive",
    "symmetric",
    "asymmetric",
    "reflexive",
    "irreflexive",
]

DataType = Literal[
    "string",
    "int",
    "float",
    "boolean",
    "datetime",
    "date",
    "time",
]


class Model(LLMDataModel):
    model_config = ConfigDict(
        frozen=True  # model is immutable by default
    )


class Description(Model):
    """Represents the description of an ontology element."""

    description: str | None = Field(
        default=None,
        description="Textual description of how to use this element. Keep this concise and only provide relevant information!",
    )
    constraints: str | None = Field(
        default=None,
        description="Constraints or rules that must be followed when using this element.",
    )

    def __hash__(self):
        return hash((self.description, self.constraints))


class DataProperty(Model):
    type: Literal["data"] = Field(
        "data", description="Set to 'data' to indicate that you are generating a data property."
    )
    name: str
    description: Description | None = None

    characteristics: list[Characteristic] = Field(default_factory=list)

    domain: list[str] = Field(default_factory=list)
    range: DataType


class ObjectProperty(Model):
    type: Literal["object"] = Field(
        "object",
        description="Set to 'object' to indicate that you are generating an object property.",
    )
    name: str
    description: Description | None = None

    characteristics: list[Characteristic] = Field(default_factory=list)

    domain: list[str] = Field(default_factory=list)
    range: list[str] = Field(default_factory=list)


class Class(Model):
    name: str
    description: Description | None = None
    own_properties: list[str]

    superclass: str | None


class Ontology(Model):
    classes: dict[str, Class] = Field(default_factory=dict)
    object_properties: dict[str, ObjectProperty] = Field(default_factory=dict)
    data_properties: dict[str, DataProperty] = Field(default_factory=dict)

    @property
    def properties(self):
        """Returns a combined dictionary of all object and data properties."""
        return dict[str, DataProperty | ObjectProperty](
            **self.object_properties, **self.data_properties
        )

    @property
    def root(
        self,
    ):  # TODO enforce a root in the first iteration of ontology generator, then we can ensure that this is never None
        """Returns the root class of the ontology, which is the class without a superclass."""
        return next((cls for cls in self.classes.values() if cls.superclass is None), None)

    def get_superclass(self, cls: Class):
        """Returns the super class of the given class, or None if it is the root."""
        return self.classes[cls.superclass] if cls.superclass is not None else None

    def get_ancestors(self, cls: Class):
        """Returns the class hierarchy chain starting from the root down to the given class."""
        chain = list[Class]()
        c = self.get_superclass(cls)

        while c is not None:
            chain.append(c)
            c = self.get_superclass(c)

        return chain

    def get_descendants(self, cls: Class):
        """Returns all descendant classes of the given class."""
        return [c for c in self.classes.values() if c.superclass == cls.name]

    def get_properties(self, cls: Class, include_inherited: bool = True):
        """Returns all properties associated with a class, optionally including inherited properties."""

        all_props = self.properties
        chain = self.get_ancestors(cls) if include_inherited else [cls]

        props = dict[str, DataProperty | ObjectProperty]()

        for c in chain:
            props.update({prop_name: all_props[prop_name] for prop_name in c.own_properties})

        return props

    def resolve_class_names(self, class_names: list[str]):
        """Resolves the given class names to class instances."""
        return [self.classes[cn] for cn in class_names]


class ClassModel(Model):
    # TODO add field and type __doc__!!!
    type: Literal["class"] = Field(
        "class", description="Set to 'class' to indicate that you are generating a class."
    )
    name: str
    description: Description | None = None
    superclass: str | None


# TODO make object and data properties models too, i.e. decouple their inter class from the generated ones like with class model
Concept = ClassModel | ObjectProperty | DataProperty
