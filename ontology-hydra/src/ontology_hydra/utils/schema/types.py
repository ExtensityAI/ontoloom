from enum import StrEnum
from typing import Annotated, Literal, NewType

from pydantic import BaseModel, ConfigDict, Field, field_validator

TypeName = NewType("TypeName", str)
PropertyName = NewType("PropertyName", str)
EnumValue = NewType("EnumValue", str)


class _Model(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)


class RefExpression(_Model):
    kind: Literal["ref"] = "ref"
    name: TypeName


class UnionExpression(_Model):
    kind: Literal["union"] = "union"
    any_of: list["TypeExpression"]

    @field_validator("any_of", mode="after")
    @classmethod
    def _disallow_optional(cls, value: list["TypeExpression"]):
        if any(isinstance(item, OptionalExpression) for item in value):
            msg = "Optional union items are not allowed; make the union optional instead."
            raise ValueError(msg)
        return value


class ListExpression(_Model):
    kind: Literal["list"] = "list"
    items: "TypeExpression"


class DictExpression(_Model):
    kind: Literal["dict"] = "dict"
    key: "TypeExpression"
    value: "TypeExpression"


class DataType(StrEnum):
    STRING = "string"
    BOOLEAN = "boolean"
    INT = "int"
    FLOAT = "float"


class PrimitiveExpression(_Model):
    kind: Literal["primitive"] = "primitive"
    dtype: DataType


class LiteralExpression(_Model):
    kind: Literal["literal"] = "literal"
    value: str | int | float | bool


class OptionalExpression(_Model):
    kind: Literal["optional"] = "optional"
    value: "TypeExpression"


TypeExpression = Annotated[
    PrimitiveExpression
    | LiteralExpression
    | RefExpression
    | UnionExpression
    | ListExpression
    | DictExpression
    | OptionalExpression,
    Field(discriminator="kind"),
]


class PropertySchema(_Model):
    description: str | None = None
    type: TypeExpression


class TypeSchema(_Model):
    description: str | None = None


class ClassTypeSchema(TypeSchema):
    type: Literal["class"] = "class"
    properties: dict[PropertyName, PropertySchema]


class EnumTypeSchema(TypeSchema):
    type: Literal["enum"] = "enum"
    values: list[EnumValue]


class Schema(ClassTypeSchema):
    name: str
    types: dict[TypeName, ClassTypeSchema | EnumTypeSchema]
