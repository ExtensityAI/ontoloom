from __future__ import annotations

import re
from typing import ClassVar, override

from ontoloom.models import TypedStr
from ontoloom.owl.iri import IRI_PATTERN

_VAR_PATTERN = re.compile(r"^\?[a-zA-Z_][a-zA-Z0-9_]*$")


class Slot(TypedStr):
    """A pattern slot: concrete IRI, variable (?name), or wildcard (*).

    - "ex:Dog"  -> concrete IRI (validated)
    - "?C"      -> variable (binds to matched value)
    - "*"       -> wildcard (matches anything, no binding)

    Slot is a `str` subclass, not a Pydantic model -> it intentionally carries
    no `type` discriminator. Generated `T | Slot` unions (e.g. `IRI | Slot`,
    `DataRange | Slot`, `TypedLiteral | LangLiteral | Slot`) rely on structural
    disambiguation: Pydantic sees a JSON string and routes to `Slot`; an object
    routes to the model variant. This is reliable because every non-Slot member
    of these unions is a Pydantic model (or dict on the wire), never a bare
    string.
    """

    description: ClassVar[str] = 'IRI ("prefix:name"), variable ("?name"), or wildcard ("*")'
    examples: ClassVar[tuple[str, ...]] = ("ex:Dog", "?C", "*")

    @classmethod
    @override
    def parse(cls, value: str) -> str:
        if value == "*":
            return value
        if value.startswith("?"):
            if not _VAR_PATTERN.match(value):
                msg = f"Variable must be ?identifier, got {value!r}"
                raise ValueError(msg)
            return value
        if not IRI_PATTERN.match(value):
            msg = f"Slot must be IRI (prefix:name), ?variable, or *, got {value!r}"
            raise ValueError(msg)
        return value

    @property
    def is_wildcard(self) -> bool:
        return self == "*"

    @property
    def is_variable(self) -> bool:
        return self.startswith("?")

    @property
    def is_iri(self) -> bool:
        return not self.is_wildcard and not self.is_variable

    @property
    def var_name(self) -> str:
        return self[1:]
