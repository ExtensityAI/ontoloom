"""Canonical normalization for OWL 2 axioms.

OWL 2 treats certain axiom fields as unordered sets (e.g. EquivalentClasses).
This module walks model_fields metadata to find Unordered() markers and sorts
those fields before serialization. All other fields pass through.

Used by content hashing (`hashing.py`) and structural matching (`patterns/`)
to compare axioms by logical content rather than authoring order.
"""

import json
from typing import Any

from pydantic import BaseModel

from ontoloom.owl.axioms import BaseAxiom
from ontoloom.owl.markers import is_unordered

# Annotations and the `negated` flag (Literal[True] tag on Negative*Assertion) aren't
# part of an axiom's logical content.
SKIP = ("annotations", "negated")


def canonical_json(axiom: BaseAxiom):
    """Deterministic JSON of an axiom's logical content, excluding annotations."""
    normalized = _normalize_model(axiom)
    return json.dumps(
        normalized.model_dump(exclude={"annotations"}),
        sort_keys=True,
        separators=(",", ":"),
    )


def _normalize_model[T: BaseModel](model: T) -> T:
    updates: dict[str, Any] = {}

    for name, info in type(model).model_fields.items():
        if name in SKIP:
            continue
        value = _normalize_value(getattr(model, name))
        if isinstance(value, tuple) and is_unordered(info):
            value = tuple(sorted(value, key=_sort_key))
        updates[name] = value
    return model.model_copy(update=updates)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize_model(value)
    if isinstance(value, tuple):
        return tuple(_normalize_value(v) for v in value)
    if isinstance(value, (str, int, float)) or value is None:
        return value
    msg = f"unhandled value {type(value).__name__} in canonical normalization"
    raise TypeError(msg)


def _sort_key(value: Any):
    if isinstance(value, str):
        return value
    data = value.model_dump() if isinstance(value, BaseModel) else value
    return json.dumps(data, sort_keys=True, separators=(",", ":"))
