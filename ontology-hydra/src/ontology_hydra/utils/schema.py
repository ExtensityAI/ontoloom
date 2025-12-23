import json
from enum import StrEnum
from typing import Annotated, Literal, NewType

from pydantic import BaseModel, ConfigDict, Field
from symai.strategy import LLMDataModel

TypeName = NewType("TypeName", str)
PropertyName = NewType("PropertyName", str)
EnumValue = NewType("EnumValue", str)


class RefExpression(BaseModel):
    kind: Literal["ref"] = "ref"
    name: TypeName


class UnionExpression(BaseModel):
    kind: Literal["union"] = "union"
    any_of: list["TypeExpression"]


class ListExpression(BaseModel):
    kind: Literal["list"] = "list"
    items: "TypeExpression"


class DataType(StrEnum):
    STRING = "string"
    BOOLEAN = "boolean"
    INT = "int"
    FLOAT = "float"


class PrimitiveExpression(BaseModel):
    kind: Literal["primitive"] = "primitive"
    dtype: DataType


class LiteralExpression(BaseModel):
    kind: Literal["literal"] = "literal"
    value: str | int | float | bool | None


TypeExpression = Annotated[
    PrimitiveExpression | LiteralExpression | RefExpression | UnionExpression | ListExpression,
    Field(discriminator="kind"),
]


class PropertySchema(BaseModel):
    description: str | None = None
    type: TypeExpression


class TypeSchema(BaseModel):
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


def _is_null_literal(expr: TypeExpression) -> bool:
    return isinstance(expr, LiteralExpression) and expr.value is None


def _unwrap_optional(expr: TypeExpression) -> tuple[bool, TypeExpression]:
    if isinstance(expr, UnionExpression):
        non_null = [item for item in expr.any_of if not _is_null_literal(item)]
        if len(non_null) != len(expr.any_of):
            if len(non_null) == 1:
                return True, non_null[0]
            return True, UnionExpression(any_of=non_null)
    return False, expr


def _format_type_inline(expr: TypeExpression) -> str:
    if isinstance(expr, PrimitiveExpression):
        return expr.dtype.value
    if isinstance(expr, LiteralExpression):
        return _format_literal(expr.value)
    if isinstance(expr, RefExpression):
        return f"ref[{expr.name}]"
    if isinstance(expr, ListExpression):
        items = _format_type_inline(expr.items)
        if isinstance(expr.items, UnionExpression):
            items = f"({items})"
        return f"list[{items}]"
    if isinstance(expr, UnionExpression):
        parts = [_format_type_inline(item) for item in expr.any_of]
        return " | ".join(parts)
    raise TypeError(f"Unsupported type expression: {type(expr)!r}")


def _format_properties(properties: dict[PropertyName, PropertySchema], indent: str) -> list[str]:
    lines: list[str] = []
    for name, prop in sorted(properties.items(), key=lambda item: str(item[0])):
        optional, base_expr = _unwrap_optional(prop.type)
        type_text = _format_type_inline(base_expr)
        if optional:
            if isinstance(base_expr, UnionExpression):
                type_text = f"({type_text})"
            type_text = f"optional[{type_text}]"
        line = f"{indent}{name}: {type_text}"
        if prop.description:
            line = f"{line}  # {_compact_text(prop.description)}"
        lines.append(line)
    return lines


def format_schema(schema: Schema) -> str:
    lines = ["SCHEMA (use exact field names)"]
    if schema.description:
        lines.append(f"Description: {_compact_text(schema.description)}")
    lines.append("")
    lines.append("Root:")
    if schema.properties:
        lines.append("")
        lines.extend(_format_properties(schema.properties, indent="  "))
    else:
        lines.append("  (none)")

    enum_types: list[tuple[TypeName, EnumTypeSchema]] = []
    class_types: list[tuple[TypeName, ClassTypeSchema]] = []
    for name, type_schema in schema.types.items():
        if isinstance(type_schema, EnumTypeSchema):
            enum_types.append((name, type_schema))
        else:
            class_types.append((name, type_schema))

    if enum_types or class_types:
        lines.append("")
        lines.append("Types:")

        if enum_types:
            lines.append("")
            lines.append("  Enums:")
            for name, enum_schema in sorted(enum_types, key=lambda item: str(item[0])):
                values = [_format_literal(str(value)) for value in enum_schema.values]
                values_text = " | ".join(values)
                line = f"    {name}: {values_text}"
                if enum_schema.description:
                    line = f"{line}  # {_compact_text(enum_schema.description)}"
                lines.append(line)

        if class_types:
            lines.append("")
            lines.append("  Classes:")
            sorted_classes = sorted(class_types, key=lambda item: str(item[0]))
            for index, (name, class_schema) in enumerate(sorted_classes):
                line = f"    {name}:"
                if class_schema.description:
                    line = f"{line}  # {_compact_text(class_schema.description)}"
                lines.append(line)
                lines.extend(_format_properties(class_schema.properties, indent="      "))
                if index < len(sorted_classes) - 1:
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
            type=UnionExpression(
                any_of=[
                    ListExpression(items=RefExpression(name=TypeName("User"))),
                    LiteralExpression(value=None),
                ]
            ),
        ),
        PropertyName("labels"): PropertySchema(
            type=UnionExpression(
                any_of=[
                    ListExpression(items=PrimitiveExpression(dtype=DataType.STRING)),
                    LiteralExpression(value=None),
                ]
            ),
        ),
        PropertyName("visibility"): PropertySchema(
            type=UnionExpression(
                any_of=[
                    LiteralExpression(value="public"),
                    LiteralExpression(value="internal"),
                    LiteralExpression(value="private"),
                ]
            ),
        ),
        PropertyName("metadata"): PropertySchema(
            type=UnionExpression(
                any_of=[
                    RefExpression(name=TypeName("Metadata")),
                    LiteralExpression(value=None),
                ]
            ),
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
                    type=UnionExpression(
                        any_of=[
                            ListExpression(
                                items=UnionExpression(
                                    any_of=[
                                        LiteralExpression(value="admin"),
                                        LiteralExpression(value="editor"),
                                        LiteralExpression(value="viewer"),
                                    ]
                                )
                            ),
                            LiteralExpression(value=None),
                        ]
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
                    type=UnionExpression(
                        any_of=[
                            PrimitiveExpression(dtype=DataType.STRING),
                            LiteralExpression(value=None),
                        ]
                    ),
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
                    type=UnionExpression(
                        any_of=[
                            PrimitiveExpression(dtype=DataType.STRING),
                            ListExpression(items=PrimitiveExpression(dtype=DataType.INT)),
                            LiteralExpression(value=None),
                        ]
                    ),
                ),
                PropertyName("media_type"): PropertySchema(
                    type=UnionExpression(
                        any_of=[
                            LiteralExpression(value="text/plain"),
                            LiteralExpression(value="application/json"),
                            LiteralExpression(value="image/png"),
                        ]
                    ),
                ),
            },
        ),
    },
)

print(EXAMPLE_SCHEMA.model_dump_json(exclude_none=True))

print("\n\n\n\nvs\n\n\n\n\n")
print(format_schema(EXAMPLE_SCHEMA))
