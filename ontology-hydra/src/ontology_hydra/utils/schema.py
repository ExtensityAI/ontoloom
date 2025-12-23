import json
from enum import Enum, StrEnum
from inspect import getdoc
from types import NoneType, UnionType
from typing import Annotated, Literal, NewType, Union, get_args, get_origin

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

    def format(self):
        # TODO: consider renaming to something more appropriate
        return format_schema(self)


class Model(LLMDataModel):
    model_config = ConfigDict(strict=True)


# --- Schema generation helpers ----------------------


def _description_from_doc(obj: object) -> str | None:
    doc = getdoc(obj)
    return doc or None


def _description_from_model_schema(model_type: type[BaseModel]) -> str | None:
    schema = model_type.model_json_schema()
    description = schema.get("description")
    if isinstance(description, str) and description:
        return description
    return None


def _unwrap_annotated(annotation: object) -> object:
    while get_origin(annotation) is Annotated:
        args = get_args(annotation)
        if not args:
            return annotation
        annotation = args[0]
    return annotation


def _flatten_union(expressions: list[TypeExpression]) -> list[TypeExpression]:
    flattened: list[TypeExpression] = []
    for expr in expressions:
        if isinstance(expr, UnionExpression):
            flattened.extend(expr.any_of)
        else:
            flattened.append(expr)
    return flattened


def _literal_to_expression(values: tuple[object, ...]) -> TypeExpression:
    non_none = [value for value in values if value is not None]
    if not non_none:
        msg = "Literal[None] is not supported for schema generation."
        raise ValueError(msg)
    literals = [LiteralExpression(value=value) for value in non_none]
    expr: TypeExpression
    expr = literals[0] if len(literals) == 1 else UnionExpression(any_of=literals)
    if len(non_none) != len(values):
        return OptionalExpression(value=expr)
    return expr


def _ensure_enum_schema(
    enum_type: type[Enum],
    types: dict[TypeName, ClassTypeSchema | EnumTypeSchema],
    seen_enums: set[type[Enum]],
):
    if enum_type in seen_enums:
        return
    seen_enums.add(enum_type)
    types[TypeName(enum_type.__name__)] = EnumTypeSchema(
        description=_description_from_doc(enum_type),
        values=[EnumValue(str(member.value)) for member in enum_type],
    )


def _collect_model_properties(
    model_type: type[BaseModel],
    types: dict[TypeName, ClassTypeSchema | EnumTypeSchema],
    seen_models: set[type[BaseModel]],
    seen_enums: set[type[Enum]],
) -> dict[PropertyName, PropertySchema]:
    properties: dict[PropertyName, PropertySchema] = {}
    for name, field_info in model_type.model_fields.items():
        annotation = field_info.annotation
        if annotation is None:
            msg = f"Missing type annotation for {model_type.__name__}.{name}"
            raise TypeError(msg)
        type_expr = _type_to_expression(annotation, types, seen_models, seen_enums)
        properties[PropertyName(name)] = PropertySchema(
            description=field_info.description,
            type=type_expr,
        )
    return properties


def _ensure_class_schema(
    model_type: type[BaseModel],
    types: dict[TypeName, ClassTypeSchema | EnumTypeSchema],
    seen_models: set[type[BaseModel]],
    seen_enums: set[type[Enum]],
):
    if model_type in seen_models:
        return
    seen_models.add(model_type)
    properties = _collect_model_properties(model_type, types, seen_models, seen_enums)
    types[TypeName(model_type.__name__)] = ClassTypeSchema(
        description=_description_from_model_schema(model_type),
        properties=properties,
    )


def _type_to_expression(
    annotation: object,
    types: dict[TypeName, ClassTypeSchema | EnumTypeSchema],
    seen_models: set[type[BaseModel]],
    seen_enums: set[type[Enum]],
) -> TypeExpression:
    annotation = _unwrap_annotated(annotation)
    origin = get_origin(annotation)

    if origin is Literal:
        return _literal_to_expression(get_args(annotation))

    if origin in (UnionType, Union):
        args = get_args(annotation)
        non_none = [arg for arg in args if arg is not NoneType]
        expressions = [_type_to_expression(arg, types, seen_models, seen_enums) for arg in non_none]
        expressions = _flatten_union(expressions)
        if not expressions:
            msg = "Union annotations must include at least one non-None type."
            raise TypeError(msg)
        if len(expressions) == 1:
            union_expr: TypeExpression = expressions[0]
        else:
            union_expr = UnionExpression(any_of=expressions)
        if len(non_none) != len(args):
            return OptionalExpression(value=union_expr)
        return union_expr

    if origin is list:
        args = get_args(annotation)
        if not args:
            msg = "List annotations must include an item type."
            raise TypeError(msg)
        return ListExpression(items=_type_to_expression(args[0], types, seen_models, seen_enums))

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        _ensure_class_schema(annotation, types, seen_models, seen_enums)
        return RefExpression(name=TypeName(annotation.__name__))

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        _ensure_enum_schema(annotation, types, seen_enums)
        return RefExpression(name=TypeName(annotation.__name__))

    if annotation is str:
        return PrimitiveExpression(dtype=DataType.STRING)
    if annotation is bool:
        return PrimitiveExpression(dtype=DataType.BOOLEAN)
    if annotation is int:
        return PrimitiveExpression(dtype=DataType.INT)
    if annotation is float:
        return PrimitiveExpression(dtype=DataType.FLOAT)

    msg = f"Unsupported annotation for schema generation: {annotation!r}"
    raise TypeError(msg)


def schema_from_model(model_type: type[BaseModel]) -> Schema:
    if not issubclass(model_type, BaseModel):
        msg = "schema_from_model expects a Pydantic BaseModel subclass."
        raise TypeError(msg)

    types: dict[TypeName, ClassTypeSchema | EnumTypeSchema] = {}
    seen_models: set[type[BaseModel]] = set()
    seen_enums: set[type[Enum]] = set()
    properties = _collect_model_properties(model_type, types, seen_models, seen_enums)

    return Schema(
        description=_description_from_model_schema(model_type),
        properties=properties,
        types=types,
    )


# --- Text formatting helpers -------------------------
def _compact_text(text: str):
    return " ".join(text.split())


def _with_description(line: str, description: str | None):
    if not description:
        return line
    return f"{line}  # {_compact_text(description)}"


def _format_literal(value: str | int | float | bool | None):
    return json.dumps(value, ensure_ascii=True)


def _wrap_in_parens(text: str):
    return f"({text})"


# --- Type formatting helpers ------------------------


def _wrap_if_union(expr: TypeExpression, text: str):
    return _wrap_in_parens(text) if isinstance(expr, UnionExpression) else text


def _format_optional_text(inner_text: str, inner_expr: TypeExpression):
    wrapped = _wrap_if_union(inner_expr, inner_text)
    return f"optional[{wrapped}]"


def _format_type_inline(expr: TypeExpression, enum_names: set[str]) -> str:
    if isinstance(expr, OptionalExpression):
        inner = _format_type_inline(expr.value, enum_names)
        return _format_optional_text(inner, expr.value)

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
        items = _wrap_if_union(expr.items, items)
        return f"list[{items}]"

    if isinstance(expr, UnionExpression):
        parts = [_format_type_inline(item, enum_names) for item in expr.any_of]
        return " | ".join(parts)
    msg = f"Unsupported type expression: {type(expr)!r}"
    raise TypeError(msg)


# -- Schema rendering helpers -------------------------------------


def _format_properties(
    properties: dict[PropertyName, PropertySchema],
    indent: str,
    enum_names: set[str],
):
    lines: list[str] = []
    for name, prop in sorted(properties.items(), key=lambda item: str(item[0])):
        type_text = _format_type_inline(prop.type, enum_names)
        line = _with_description(f"{indent}{name}: {type_text}", prop.description)
        lines.append(line)
    return lines


def _format_enum_values(values: list[EnumValue]):
    return " | ".join(_format_literal(str(value)) for value in values)


def _format_type_block(
    name: TypeName,
    type_schema: ClassTypeSchema | EnumTypeSchema,
    enum_names: set[str],
):
    if isinstance(type_schema, EnumTypeSchema):
        values_text = _format_enum_values(type_schema.values)
        line = _with_description(f"  {name}: {values_text}", type_schema.description)
        return [line]

    if isinstance(type_schema, ClassTypeSchema):
        line = _with_description(f"  {name}:", type_schema.description)
        return [
            line,
            *_format_properties(type_schema.properties, indent="    ", enum_names=enum_names),
        ]

    msg = f"Unknown type schema: {type_schema}"
    raise ValueError(msg)


def format_schema(schema: Schema):
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
            lines.extend(_format_type_block(name, type_schema, enum_names))

            if index < len(ordered_types) - 1:
                # add blank line between types
                lines.append("")

    return "\n".join(lines)
