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
    parent: "Class | None" = None


class OntologyState(Model):
    classes: vartuple[Class]


DEFAULT_ONTOLOGY_STATE = OntologyState(classes=(Class(name="Thing"),))
