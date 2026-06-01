"""Project-wide Pydantic base types: frozen models and validated string subclasses."""

from abc import abstractmethod
from collections.abc import Callable
from typing import Annotated, Any, ClassVar, Literal, override

from pydantic import BaseModel, ConfigDict, Discriminator, Field, GetCoreSchemaHandler, Tag
from pydantic_core import CoreSchema, core_schema

from ontoloom.errors import OntoloomError
from ontoloom.utils import dquoted


class UnionDispatchError(OntoloomError):
    """Input dict does not match any variant of a discriminated union.

    Carries the best-fit variant and the precise discrepancy so the consumer
    layer (MCP, REPL, etc.) can render a focused message instead of dumping
    every union member's signature.
    """

    def __init__(
        self,
        union_name: str,
        closest_variant: str,
        keys: frozenset[str],
        missing: frozenset[str],
        unknown: frozenset[str],
    ):
        self.union_name = union_name
        self.closest_variant = closest_variant
        self.keys = keys
        self.missing = missing
        self.unknown = unknown
        parts = [
            f"input does not match any {union_name} variant; closest: {dquoted(closest_variant)}"
        ]
        if missing:
            parts.append(f"missing required field(s) {sorted(missing)}")
        if unknown:
            parts.append(f"unknown field(s) {sorted(unknown)}")
        super().__init__("; ".join(parts))


def tagged_union_meta(
    get_tag: Callable[[Any], str],
    *,
    schema_type: Literal["object", "string"] | tuple[Literal["string"], Literal["object"]] = (
        "object"
    ),
):
    """Annotated metadata for a discriminated union: discriminator + JSON-schema type marker.

    Splat into `Annotated[A | B, *tagged_union_meta(get_tag)]`. `schema_type`
    is `"object"` for object-only unions, `"string"` for string-only unions
    (e.g. Slot), or `("string", "object")` for mixed unions.
    """
    # Without the type marker the Claude Code MCP client serializes dicts as JSON-encoded strings.
    json_schema_extra: dict[str, Any] = {"type": schema_type}
    return (Discriminator(get_tag), Field(json_schema_extra=json_schema_extra))


class FrozenModel(BaseModel):
    """Frozen Pydantic base. `cls.tag()` returns the class name — used as the
    structural-discriminator value in SQL queries and dispatch tables."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    @classmethod
    def tag(cls):
        return cls.__name__


def make_tag_resolver(
    classes: tuple[type[FrozenModel], ...],
    *,
    union_name: str,
    exclude: tuple[str, ...] = ("annotations",),
):
    """Build a Pydantic discriminator callable that picks one of `classes`
    based on which fields are present in the input.

    The Pydantic-recommended pattern for callable discriminators
    (https://docs.pydantic.dev/latest/concepts/unions/) is a hand-written
    if-chain over dict keys. This helper is the same pattern, but derives
    the dispatch from each class's `model_fields` so renaming a field can't
    silently misroute raw-dict input.

    A dict matches class `C` iff `required(C) ⊆ keys ⊆ full(C)` — i.e. the
    input has every required field of `C` and no field that `C` doesn't
    declare. If two classes match (e.g. `OPA` vs `NegativeOPA` when input
    omits `negated`), the one with the smaller declared-field set wins —
    "the most specific fit explains the input". Stable on ties: the first
    class in `classes` order wins.

    `union_name` labels the union in error messages (e.g. "Axiom", "Pattern").

    Raises `UnionDispatchError` on no match, naming the best-fit variant and
    the precise missing/unknown fields. The error is an `OntoloomError`, so
    Pydantic propagates it untouched (only `ValueError`/`AssertionError` get
    wrapped as `ValidationError`).
    """
    excluded = frozenset(exclude)

    # Pre-compute (cls, required-fields, full-fields) per class once at module
    # load time. The dispatch loop only does set operations against these.
    sigs = tuple(
        (
            cls,
            frozenset(
                f
                for f, info in cls.model_fields.items()
                if info.is_required() and f not in excluded
            ),
            frozenset(cls.model_fields) - excluded,
        )
        for cls in classes
    )

    def get_tag(v: Any):
        # Already-validated model instance: dispatch by class identity.
        if not isinstance(v, dict):
            return type(v).__name__

        keys = frozenset(v) - excluded
        matches = [(cls, full) for cls, req, full in sigs if req <= keys <= full]
        if matches:
            # Smallest full-field set = tightest fit for the input. Pydantic's
            # `min` is stable, so identical-size matches resolve to the class
            # listed first in `classes`.
            cls, _ = min(matches, key=lambda m: len(m[1]))
            return cls.tag()

        # No class fits. Score each candidate by how close it is to `keys`:
        # most required fields satisfied, then fewest unknown keys, then
        # fewest missing required. Stable on ties (first-listed wins).
        best_cls, best_req, best_full = max(
            sigs,
            key=lambda s: (len(s[1] & keys), -len(keys - s[2]), -len(s[1] - keys)),
        )
        raise UnionDispatchError(
            union_name=union_name,
            closest_variant=best_cls.tag(),
            keys=keys,
            missing=best_req - keys,
            unknown=keys - best_full,
        )

    return get_tag


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
    def tag(cls):
        return cls.__name__

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


def tagged[T: FrozenModel | TypedStr](cls: type[T], *extras: Any) -> type[T]:
    """Build `Annotated[cls, Tag(cls.tag()), *extras]` — the per-member shape used inside discriminated unions."""
    return Annotated[cls, Tag(cls.tag()), *extras]  # pyright: ignore[reportReturnType]
