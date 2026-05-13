"""Pattern slot types: wildcard `*`, variable `?name`, or concrete IRI.

`Slot` is a discriminated union over `WildcardSlot | VariableSlot | IRISlot`;
Pydantic dispatches by string content via a callable discriminator. Wire form
is a single string with one of three disjoint shapes.

`BaseSlot` is the runtime parent class — use `isinstance(x, BaseSlot)` to check
"is this any slot type."
"""

from __future__ import annotations

import re
from typing import Annotated, Any, override

from ontoloom.models import TypedStr, tagged, tagged_union_meta
from ontoloom.owl.iri import IRI
from ontoloom.utils import dquoted

_VAR_PATTERN = re.compile(r"^\?[a-zA-Z_][a-zA-Z0-9_]*$")


class BaseSlot(TypedStr):
    """Runtime parent for the three slot variants. Never instantiated directly."""


class WildcardSlot(BaseSlot):
    """Pattern slot matching any value without binding."""

    description = 'Wildcard pattern slot, literal "*"'
    pattern = r"^\*$"
    examples = ("*",)

    @override
    @classmethod
    def parse(cls, value: str):
        if value != "*":
            msg = f'WildcardSlot must be "*", got {dquoted(value)}'
            raise ValueError(msg)
        return value


class VariableSlot(BaseSlot):
    """Pattern slot that binds to its matched value across positions."""

    description = 'Variable pattern slot, "?name"'
    pattern = r"^\?[a-zA-Z_][a-zA-Z0-9_]*$"
    examples = ("?C", "?prop")

    @override
    @classmethod
    def parse(cls, value: str):
        if not _VAR_PATTERN.match(value):
            msg = f'VariableSlot must be "?identifier", got {dquoted(value)}'
            raise ValueError(msg)
        return value

    @property
    def name(self):
        return self[1:]


class IRISlot(BaseSlot):
    """Concrete IRI used in a pattern position. Same validation as `IRI`."""

    description = IRI.description
    pattern = IRI.pattern
    examples = IRI.examples

    @override
    @classmethod
    def parse(cls, value: str):
        return IRI.parse(value)


def _get_slot_tag(v: Any):
    if isinstance(v, BaseSlot):
        return type(v).tag()

    if isinstance(v, str):
        if v == "*":
            return WildcardSlot.tag()
        if v.startswith("?"):
            return VariableSlot.tag()
        return IRISlot.tag()

    # Non-string, non-slot input. Returning a non-matching tag makes Pydantic
    # raise ValidationError for this branch and fall back to the next branch
    # of any outer union (e.g. `TypedLiteral | LangLiteral | Slot`).
    return ""


Slot = Annotated[
    tagged(WildcardSlot) | tagged(VariableSlot) | tagged(IRISlot),
    *tagged_union_meta(_get_slot_tag, schema_type="string"),
]
