from __future__ import annotations

import re
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

_IRI_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_.-]*)?:[^\x00-\x1f]+$")
_VAR_RE = re.compile(r"^\?[a-zA-Z_][a-zA-Z0-9_]*$")


class Slot(str):
    """A pattern slot: concrete IRI, variable (?name), or wildcard (*).

    - "ex:Dog"  → concrete IRI (validated)
    - "?C"      → variable (binds to matched value)
    - "*"       → wildcard (matches anything, no binding)
    """

    def __new__(cls, value: str):
        if value == "*":
            pass
        elif value.startswith("?"):
            if not _VAR_RE.match(value):
                msg = f"Variable must be ?identifier, got {value!r}"
                raise ValueError(msg)
        else:
            if not _IRI_RE.match(value):
                msg = f"Slot must be IRI (prefix:name), ?variable, or *, got {value!r}"
                raise ValueError(msg)
        return str.__new__(cls, value)

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

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: Any, handler: Any) -> dict[str, Any]:
        return {
            "type": "string",
            "description": 'IRI ("prefix:name"), variable ("?name"), or wildcard ("*")',
            "examples": ["ex:Dog", "?C", "*"],
        }
