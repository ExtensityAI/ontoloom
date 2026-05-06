"""Project-wide Pydantic base types: frozen models and validated string subclasses."""

from abc import abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar, get_args, override

from pydantic import BaseModel, ConfigDict, Discriminator, Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


# Pydantic emits `oneOf + discriminator` for tagged unions but no outer
# `type` constraint (each branch carries its own). Claude Code's MCP client falls
# back to JSON-string serialization when a param schema lacks an explicit `type`
# at the top, so the server receives a string instead of a dict. The `type` schema
# keyword is a no-op for validation but tells the client to send a structured
# value (or string, if the union accepts both). Defaults preserve object-only behavior.
def tagged_union_meta(
    disc: str | Callable[[Any], str] = "type",
    schema_type: str | list[str] = "object",
):
    """Annotated metadata for a top-level discriminated union exposed as an MCP tool param.

    Splat into Annotated: `Annotated[A | B, *tagged_union_meta()]`.

    Args:
        disc: Discriminator field name (string) or callable that extracts the tag
              from raw input (string, dict, or model instance). Defaults to "type".
        schema_type: JSON schema `type` value: "object" for object-only unions,
                     ["string", "object"] for string-or-object unions, etc.
                     Defaults to "object".
    """
    json_schema_extra: dict[str, Any] = {"type": schema_type}
    return (Discriminator(disc), Field(json_schema_extra=json_schema_extra))


class FrozenModel(BaseModel):
    """Frozen Pydantic base. Subclasses with a `type: Literal["X"] = "X"` field
    automatically gain a `type_: ClassVar[str]` set to the literal value, used
    as the discriminator key in SQL queries and dispatch tables."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type_: ClassVar[str]

    @override
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        field = cls.model_fields.get("type")
        if field is None:
            return
        literal_args = get_args(field.annotation)
        if literal_args and isinstance(literal_args[0], str):
            cls.type_ = literal_args[0]


class TypedStr(str):
    """Base for `str` subclasses with construction-time validation.

    Subclasses override `parse` to validate and normalize input. Optional class
    vars (`description`, `pattern`, `examples`) feed the JSON schema Pydantic
    emits for tool-arg documentation; they are descriptive only -> actual
    validation lives in `parse`.
    """

    description: ClassVar[str] = ""
    pattern: ClassVar[str] = ""
    examples: ClassVar[tuple[str, ...]] = ()

    @classmethod
    @abstractmethod
    def parse(cls, value: str) -> str:
        """Validate and normalize `value`. Raise ValueError on invalid input. Return canonical form."""
        raise NotImplementedError

    def __new__(cls, value: str):
        return super().__new__(cls, cls.parse(value))

    @override
    def __repr__(self):
        return f"{type(self).__name__}({self})"

    @classmethod
    def __get_pydantic_core_schema__(cls, _: Any, __: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
            ref=cls.__name__,
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: Any, handler: Any) -> dict[str, Any]:
        json_schema = handler(schema)
        target = handler.resolve_ref_schema(json_schema)
        target.setdefault("type", "string")

        if cls.description:
            target.setdefault("description", cls.description)

        if cls.pattern:
            target.setdefault("pattern", cls.pattern)

        if cls.examples:
            target.setdefault("examples", list(cls.examples))

        return json_schema
