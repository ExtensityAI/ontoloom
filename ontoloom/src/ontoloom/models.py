"""Project-wide Pydantic base types: frozen models and validated string subclasses."""

from abc import abstractmethod
from typing import Any, ClassVar, get_args, override

from pydantic import BaseModel, ConfigDict, Discriminator, Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


# Pydantic emits `oneOf + discriminator` for tagged unions but no outer
# `type: "object"` (each branch carries its own). Claude Code's MCP client falls
# back to JSON-string serialization when a param schema lacks an explicit `type`
# at the top, so the server receives a string instead of a dict. Adding
# `type: "object"` is a no-op for validation but tells the client to send a
# structured value.
def tagged_union_meta():
    """Annotated metadata for a top-level discriminated union exposed as an MCP tool param.

    Splat into Annotated: `Annotated[A | B, *tagged_union_meta()]`.
    """
    return (Discriminator("type"), Field(json_schema_extra={"type": "object"}))


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
