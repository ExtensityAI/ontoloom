"""Pydantic infrastructure shared by ontology models. Not OWL-specific."""

from typing import Any, ClassVar, override

from pydantic import BaseModel, ConfigDict, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TaggedModel(FrozenModel):
    """A FrozenModel that participates in a discriminated union via a `type` field.

    Concrete subclasses declare `type: Literal["..."] = "..."`. Intermediate bases
    that don't declare their own `type` are skipped silently. The literal default
    is mirrored to a `type_` ClassVar — read it (instead of `instance.type`) when
    static-typing against an abstract base, since pyright can't see the `type`
    field on `TaggedModel` itself. `Declaration.type_` and `instance.type_` both
    return the same string at runtime.
    """

    type_: ClassVar[str] = ""

    @override
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        if "type" not in cls.__annotations__:
            return
        default = cls.model_fields["type"].default
        if not isinstance(default, str) or not default:
            msg = f'{cls.__name__}.type must be Literal["..."] = "..." with a non-empty str default'
            raise TypeError(msg)
        cls.type_ = default


class _PydanticStr(str):
    """Base for str subclasses that Pydantic should validate as plain strings."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())
