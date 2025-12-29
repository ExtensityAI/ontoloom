import json

from ontology_hydra.utils.schema.types import (
    ClassTypeSchema,
    EnumTypeSchema,
    EnumValue,
    ListExpression,
    LiteralExpression,
    OptionalExpression,
    PrimitiveExpression,
    PropertyName,
    PropertySchema,
    RefExpression,
    Schema,
    TypeExpression,
    TypeName,
    UnionExpression,
)

# --- Text formatting helpers -------------------------


def _compact_text(text: str):
    return " ".join(text.split())


def _append_description(line: str, description: str | None):
    if not description:
        return line

    return f"{line}  # {_compact_text(description)}"


def _format_literal(value: str | int | float | bool | None):
    # we do not want Python-formatting (e.g. True, False, None), thus format with JSON
    return json.dumps(value, ensure_ascii=True)


# --- Type formatting helpers ------------------------


def _wrap_if_union(expr: TypeExpression, text: str):
    # if the expression is a union, wrap it in parentheses to improve readability
    return f"({text})" if isinstance(expr, UnionExpression) else text


def _format_type_inline(expr: TypeExpression, enum_names: set[str]) -> str:
    match expr:
        case OptionalExpression():
            # wrap formatted inner type with optional[...] and also add parentheses if union
            inner = _format_type_inline(expr.value, enum_names)
            return f"optional[{_wrap_if_union(expr.value, inner)}]"

        case PrimitiveExpression():
            # name of data type
            return expr.dtype.value

        case LiteralExpression():
            # JSON-formatted literal
            return _format_literal(expr.value)

        case RefExpression():
            if expr.name in enum_names:
                # if enum, we do not need a ref[...] as enums are like simple data types
                # TODO: reconsider
                return str(expr.name)

            return f"ref[{expr.name}]"

        case ListExpression():
            inner = _wrap_if_union(expr.items, _format_type_inline(expr.items, enum_names))
            return f"list[{inner}]"

        case UnionExpression():
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
    lines = list[str]()

    # format props sorted by name
    for name, prop in sorted(properties.items(), key=lambda item: str(item[0])):
        type_text = _format_type_inline(prop.type, enum_names)
        line = _append_description(f"{indent}{name}: {type_text}", prop.description)
        lines.append(line)

    return lines


def _format_enum_values(values: list[EnumValue]):
    return " | ".join(_format_literal(str(value)) for value in values)


def _format_type_block(
    name: TypeName,
    type_schema: ClassTypeSchema | EnumTypeSchema,
    enum_names: set[str],
):
    match type_schema:
        case EnumTypeSchema():
            values_text = _format_enum_values(type_schema.values)
            line = _append_description(f"  {name}: {values_text}", type_schema.description)
            return [line]

        case ClassTypeSchema():
            line = _append_description(f"  {name}:", type_schema.description)
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
    lines.append(f"{schema.name}:")

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
