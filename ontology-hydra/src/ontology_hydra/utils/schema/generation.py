from enum import Enum
from types import NoneType, UnionType
from typing import TYPE_CHECKING, Annotated, Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

from ontology_hydra.utils.schema.types import (
    ClassTypeSchema,
    DataType,
    DictExpression,
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

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

_PRIMITIVE_TYPES: tuple[tuple[type, DataType], ...] = (
    (bool, DataType.BOOLEAN),
    (int, DataType.INT),
    (float, DataType.FLOAT),
    (str, DataType.STRING),
)


def _unwrap_annotated(annotation: Any):
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _unwrap_newtype(annotation: Any):
    while hasattr(annotation, "__supertype__"):
        annotation = annotation.__supertype__
    return annotation


def _map_to_datatype(annotation: Any):
    if not isinstance(annotation, type):
        return None

    for py_type, dtype in _PRIMITIVE_TYPES:
        if issubclass(annotation, py_type):
            return dtype

    return None


def _literal_value_expression(value: Any):
    if isinstance(value, bool | int | float | str):
        return LiteralExpression(value=value)

    msg = f"Unsupported Literal value type: {type(value)!r}"
    raise TypeError(msg)


def _combine_union(expressions: list[TypeExpression]):
    # this does not support nested unions for now, but can be easily extended if necessary

    flattened = list[TypeExpression]()

    for expr in expressions:
        if isinstance(expr, UnionExpression):
            flattened.extend(expr.any_of)
        else:
            flattened.append(expr)

    if not flattened:
        msg = "Union types must include at least one non-null member."
        raise TypeError(msg)

    if len(flattened) == 1:
        return flattened[0]

    return UnionExpression(any_of=flattened)


def _register_enum_type(
    enum_type: type[Enum],
    type_schemas: dict[TypeName, ClassTypeSchema | EnumTypeSchema],
):
    name = TypeName(enum_type.__name__)
    existing = type_schemas.get(name)

    if existing is not None:
        if not isinstance(existing, EnumTypeSchema):
            msg = f"Type name {name} is already used for a class schema."
            raise TypeError(msg)
        return

    values = []
    for item in enum_type:
        if not isinstance(item.value, str):
            msg = f"Enum {enum_type.__name__} must use string values."
            raise TypeError(msg)

        values.append(EnumValue(item.value))

    type_schemas[name] = EnumTypeSchema(description=enum_type.__doc__, values=values)


def _register_class_type(
    model_type: type[BaseModel],
    type_schemas: dict[TypeName, ClassTypeSchema | EnumTypeSchema],
    seen_models: set[type[BaseModel]],
):
    name = TypeName(model_type.__name__)
    existing = type_schemas.get(name)

    if existing is not None:
        if not isinstance(existing, ClassTypeSchema):
            msg = f"Type name {name} is already used for an enum schema."
            raise TypeError(msg)
        return

    if model_type in seen_models:
        return
    seen_models.add(model_type)

    try:
        properties = {
            PropertyName(name): _generate_property_schema(field, type_schemas, seen_models)
            for name, field in model_type.model_fields.items()
            if name != "section_header"  # exclude LLMDataModel default section_header prop
        }
    finally:
        seen_models.remove(model_type)

    type_schemas[name] = ClassTypeSchema(
        description=model_type.__doc__,
        properties=properties,
    )


def _type_expression_from_origin(
    annotation: Any,
    origin: Any,
    type_schemas: dict[TypeName, ClassTypeSchema | EnumTypeSchema],
    seen_models: set[type[BaseModel]],
):
    if origin is Literal:
        literal_values = get_args(annotation)
        return _combine_union([_literal_value_expression(value) for value in literal_values])

    if origin is list:
        args = get_args(annotation)
        if len(args) != 1:
            msg = "List types must include exactly one item type."
            raise TypeError(msg)
        return ListExpression(items=_type_expression(args[0], type_schemas, seen_models))

    if origin is dict:
        args = get_args(annotation)
        if len(args) != 2:
            msg = "Dict types must include exactly one key type and one value type."
            raise TypeError(msg)
        key_expr = _type_expression(args[0], type_schemas, seen_models)
        value_expr = _type_expression(args[1], type_schemas, seen_models)
        return DictExpression(key=key_expr, value=value_expr)

    if origin in {Union, UnionType}:
        # need to use deprecated `Union` type here as this seems to be returned by get_origin
        args = get_args(annotation)
        non_none = [arg for arg in args if arg is not NoneType]
        has_none = len(non_none) != len(args)
        combined = _combine_union(
            [_type_expression(arg, type_schemas, seen_models) for arg in non_none],
        )
        return OptionalExpression(value=combined) if has_none else combined

    return None


def _type_expression(
    annotation: Any,
    type_schemas: dict[TypeName, ClassTypeSchema | EnumTypeSchema],
    seen_models: set[type[BaseModel]],
):
    annotation = _unwrap_newtype(_unwrap_annotated(annotation))

    if annotation is Any:
        msg = "Any is not supported in schema generation."
        raise TypeError(msg)

    origin = get_origin(annotation)
    if expression := _type_expression_from_origin(
        annotation,
        origin,
        type_schemas,
        seen_models,
    ):
        return expression

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        # field is a pydantic model
        _register_class_type(annotation, type_schemas, seen_models)
        return RefExpression(name=TypeName(annotation.__name__))

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        # field is an enum
        _register_enum_type(annotation, type_schemas)
        return RefExpression(name=TypeName(annotation.__name__))

    if (dtype := _map_to_datatype(annotation)) is not None:
        # field is just a primitive data type
        return PrimitiveExpression(dtype=dtype)

    msg = f"Unsupported annotation: {annotation!r}"
    raise TypeError(msg)


def _generate_property_schema(
    field: FieldInfo,
    type_schemas: dict[TypeName, ClassTypeSchema | EnumTypeSchema],
    seen_models: set[type[BaseModel]],
):
    if (annotation := field.annotation) is None:
        msg = "Field annotations must be declared for schema generation."
        raise TypeError(msg)

    return PropertySchema(
        description=field.description,
        type=_type_expression(annotation, type_schemas, seen_models),
    )


def schema_from_model(model_type: type[BaseModel]) -> Schema:
    if not issubclass(model_type, BaseModel):
        msg = "schema_from_model expects a Pydantic BaseModel subclass."
        raise TypeError(msg)

    type_schemas: dict[TypeName, ClassTypeSchema | EnumTypeSchema] = {}
    seen_models: set[type[BaseModel]] = set()

    properties = {
        PropertyName(name): _generate_property_schema(field, type_schemas, seen_models)
        for name, field in model_type.model_fields.items()
        if name != "section_header"  # exclude LLMDataModel default section_header property
    }

    return Schema(
        name=model_type.__name__,
        description=model_type.__doc__,
        properties=properties,
        types=type_schemas,
    )
