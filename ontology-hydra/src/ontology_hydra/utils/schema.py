import json
from enum import StrEnum
from typing import Annotated, Literal, NewType

from pydantic import BaseModel, ConfigDict, Field, field_validator
from symai.strategy import LLMDataModel

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
            msg = (
                "OptionalExpression is not allowed inside UnionExpression; wrap the union "
                "in OptionalExpression instead."
            )
            raise ValueError(msg)
        return value


class ListExpression(_Model):
    kind: Literal["list"] = "list"
    items: "TypeExpression"


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
    types: dict[TypeName, ClassTypeSchema | EnumTypeSchema]


class Model(LLMDataModel):
    model_config = ConfigDict(strict=True)


def _compact_text(text: str) -> str:
    return " ".join(text.split())


def _format_literal(value: str | int | float | bool | None) -> str:
    return json.dumps(value, ensure_ascii=True)


def _paranthesized(value: str):
    return f"({value})"


def _unwrap_optional(expr: TypeExpression) -> tuple[bool, TypeExpression]:
    if isinstance(expr, OptionalExpression):
        return True, expr.value

    return False, expr


def _format_type_inline(expr: TypeExpression, enum_names: set[str]) -> str:
    if isinstance(expr, OptionalExpression):
        inner = _format_type_inline(expr.value, enum_names)

        if isinstance(expr.value, UnionExpression):
            # TODO: consider omitting ()
            inner = _paranthesized(inner)

        return f"optional[{inner}]"

    if isinstance(expr, PrimitiveExpression):
        return expr.dtype.value

    if isinstance(expr, LiteralExpression):
        return _format_literal(expr.value)

    if isinstance(expr, RefExpression):
        name = str(expr.name)
        if name in enum_names:
            return name
        return f"ref[{name}]"

    if isinstance(expr, ListExpression):
        items = _format_type_inline(expr.items, enum_names)
        if isinstance(expr.items, UnionExpression):
            items = _paranthesized(items)
        return f"list[{items}]"

    if isinstance(expr, UnionExpression):
        parts = [_format_type_inline(item, enum_names) for item in expr.any_of]
        return " | ".join(parts)
    msg = f"Unsupported type expression: {type(expr)!r}"
    raise TypeError(msg)


def _format_property_type(expr: TypeExpression, enum_names: set[str]) -> str:
    optional, base_expr = _unwrap_optional(expr)
    type_text = _format_type_inline(base_expr, enum_names)

    if optional:
        if isinstance(base_expr, UnionExpression):
            type_text = _paranthesized(type_text)
        type_text = f"optional[{type_text}]"

    return type_text


def _format_properties(
    properties: dict[PropertyName, PropertySchema],
    indent: str,
    enum_names: set[str],
) -> list[str]:
    lines: list[str] = []
    for name, prop in sorted(properties.items(), key=lambda item: str(item[0])):
        type_text = _format_property_type(prop.type, enum_names)
        line = f"{indent}{name}: {type_text}"
        if prop.description:
            line = f"{line}  # {_compact_text(prop.description)}"
        lines.append(line)
    return lines


def format_schema(schema: Schema) -> str:
    lines = ["[[SCHEMA]] (use exact field names)"]

    if schema.description:
        lines.append(f"Description: {_compact_text(schema.description)}")

    lines.append("")
    lines.append("Root:")

    enum_names = {str(name) for name, t in schema.types.items() if isinstance(t, EnumTypeSchema)}

    if schema.properties:
        lines.extend(_format_properties(schema.properties, indent="  ", enum_names=enum_names))
    else:
        lines.append("  (none)")

    if schema.types:
        lines.append("")
        lines.append("Types:")

        ordered_types = sorted(schema.types.items(), key=lambda item: str(item[0]))

        for index, (name, type_schema) in enumerate(ordered_types):
            if isinstance(type_schema, EnumTypeSchema):
                # format enum
                values = [_format_literal(str(value)) for value in type_schema.values]
                values_text = " | ".join(values)
                line = f"  {name}: {values_text}"

                if type_schema.description:
                    line = f"{line}  # {_compact_text(type_schema.description)}"

                lines.append(line)

            elif isinstance(type_schema, ClassTypeSchema):
                # format class type
                line = f"  {name}:"

                if type_schema.description:
                    line = f"{line}  # {_compact_text(type_schema.description)}"

                lines.append(line)
                lines.extend(
                    _format_properties(type_schema.properties, indent="    ", enum_names=enum_names)
                )
            else:
                msg = f"Unknown type schema: {type_schema}"
                raise ValueError(msg)

            if index < len(ordered_types) - 1:
                # add blank line between types
                lines.append("")

    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


EXAMPLE_SCHEMA = Schema(
    description="Example schema exercising ref, union, list, primitive, and literal types.",
    properties={
        PropertyName("id"): PropertySchema(
            description="Stable document identifier.",
            type=PrimitiveExpression(dtype=DataType.STRING),
        ),
        PropertyName("status"): PropertySchema(
            type=RefExpression(name=TypeName("Status")),
        ),
        PropertyName("owner"): PropertySchema(
            type=RefExpression(name=TypeName("User")),
        ),
        PropertyName("contributors"): PropertySchema(
            type=OptionalExpression(
                value=ListExpression(items=RefExpression(name=TypeName("User")))
            ),
        ),
        PropertyName("labels"): PropertySchema(
            type=OptionalExpression(
                value=ListExpression(items=PrimitiveExpression(dtype=DataType.STRING))
            ),
        ),
        PropertyName("visibility"): PropertySchema(
            type=RefExpression(name=TypeName("Visibility")),
        ),
        PropertyName("metadata"): PropertySchema(
            type=OptionalExpression(value=RefExpression(name=TypeName("Metadata"))),
        ),
        PropertyName("attachments"): PropertySchema(
            type=ListExpression(items=RefExpression(name=TypeName("Attachment"))),
        ),
    },
    types={
        TypeName("Status"): EnumTypeSchema(
            description="Workflow state for a document.",
            values=[
                EnumValue("draft"),
                EnumValue("review"),
                EnumValue("published"),
            ],
        ),
        TypeName("Visibility"): EnumTypeSchema(
            description="Access level for the document.",
            values=[
                EnumValue("public"),
                EnumValue("internal"),
                EnumValue("private"),
            ],
        ),
        TypeName("MediaType"): EnumTypeSchema(
            description="MIME types supported for attachments.",
            values=[
                EnumValue("text/plain"),
                EnumValue("application/json"),
                EnumValue("image/png"),
            ],
        ),
        TypeName("Role"): EnumTypeSchema(
            description="Account role used for access control.",
            values=[
                EnumValue("admin"),
                EnumValue("editor"),
                EnumValue("viewer"),
            ],
        ),
        TypeName("User"): ClassTypeSchema(
            description="Account holder with role assignments.",
            properties={
                PropertyName("user_id"): PropertySchema(
                    type=PrimitiveExpression(dtype=DataType.STRING),
                ),
                PropertyName("email"): PropertySchema(
                    type=PrimitiveExpression(dtype=DataType.STRING),
                ),
                PropertyName("roles"): PropertySchema(
                    type=OptionalExpression(
                        value=ListExpression(items=RefExpression(name=TypeName("Role")))
                    ),
                ),
            },
        ),
        TypeName("Metadata"): ClassTypeSchema(
            description="Structured metadata with mixed literals and primitives.",
            properties={
                PropertyName("version"): PropertySchema(
                    type=UnionExpression(
                        any_of=[
                            PrimitiveExpression(dtype=DataType.INT),
                            LiteralExpression(value="v1"),
                            LiteralExpression(value="v2"),
                        ]
                    ),
                ),
                PropertyName("checksum"): PropertySchema(
                    type=OptionalExpression(value=PrimitiveExpression(dtype=DataType.STRING)),
                ),
            },
        ),
        TypeName("Attachment"): ClassTypeSchema(
            description="Binary or textual attachments for a document.",
            properties={
                PropertyName("filename"): PropertySchema(
                    type=PrimitiveExpression(dtype=DataType.STRING),
                ),
                PropertyName("size_bytes"): PropertySchema(
                    type=PrimitiveExpression(dtype=DataType.INT),
                ),
                PropertyName("content"): PropertySchema(
                    type=OptionalExpression(
                        value=UnionExpression(
                            any_of=[
                                PrimitiveExpression(dtype=DataType.STRING),
                                ListExpression(items=PrimitiveExpression(dtype=DataType.INT)),
                            ]
                        )
                    ),
                ),
                PropertyName("media_type"): PropertySchema(
                    type=RefExpression(name=TypeName("MediaType")),
                ),
            },
        ),
    },
)


# Example Pydantic models derived from EXAMPLE_SCHEMA.
class Status(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"


class Visibility(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"


class MediaType(StrEnum):
    TEXT_PLAIN = "text/plain"
    APPLICATION_JSON = "application/json"
    IMAGE_PNG = "image/png"


class Role(StrEnum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class UserModel(BaseModel):
    model_config = ConfigDict(strict=True)

    user_id: str
    email: str
    roles: list[Role] | None = None


class MetadataModel(BaseModel):
    model_config = ConfigDict(strict=True)

    version: int | Literal["v1", "v2"]
    checksum: str | None = None


class AttachmentModel(BaseModel):
    model_config = ConfigDict(strict=True)

    filename: str
    size_bytes: int
    content: str | list[int] | None = None
    media_type: MediaType


class ExampleRootModel(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    status: Status
    owner: UserModel
    contributors: list[UserModel] | None = None
    labels: list[str] | None = None
    visibility: Visibility
    metadata: MetadataModel | None = None
    attachments: list[AttachmentModel]


print(EXAMPLE_SCHEMA.model_dump_json(exclude_none=True))

print("\n\n\n\nvs\n\n\n\n\n")
print(format_schema(EXAMPLE_SCHEMA))
