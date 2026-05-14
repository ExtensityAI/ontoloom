"""Pydantic-friendly wire types for selection references.

`SelectionRef` and `LockedSelectionRef` are dataclasses; Pydantic would default
to an object shape in their JSON schema. The `BeforeValidator` parses the wire
string into the dataclass at validation time, and `WithJsonSchema` declares the
wire shape as `{"type": "string", "pattern": ...}` so LLM tool callers see a
string parameter.
"""

from typing import Annotated

from ontoloom.query._selection_ref import LockedSelectionRef, SelectionRef
from pydantic import BeforeValidator, WithJsonSchema

_SELECTION_REF_SCHEMA = {
    "type": "string",
    "pattern": r"^(axioms|entities):.+$",
    "description": "Selection reference as 'kind:bare_name' (e.g. 'axioms:my_axioms', 'entities:my_classes')",
    "examples": ["axioms:my_axioms", "entities:my_classes"],
}

_LOCKED_SELECTION_REF_SCHEMA = {
    "type": "string",
    "pattern": r"^(axioms|entities):.+@[0-9a-fA-F]{8,}$",
    "description": "Locked selection reference as 'kind:bare_name@hash_prefix' (e.g. 'axioms:my_axioms@a3f1b2c4')",
    "examples": ["axioms:my_axioms@a3f1b2c4"],
}

SelectionRefParam = Annotated[
    SelectionRef,
    BeforeValidator(SelectionRef.parse),
    WithJsonSchema(_SELECTION_REF_SCHEMA),
]

LockedSelectionRefParam = Annotated[
    LockedSelectionRef,
    BeforeValidator(LockedSelectionRef.parse),
    WithJsonSchema(_LOCKED_SELECTION_REF_SCHEMA),
]
