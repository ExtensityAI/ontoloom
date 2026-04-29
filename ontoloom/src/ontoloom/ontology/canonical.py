"""Canonical normalization and content hashing for OWL 2 axioms.

OWL 2 treats certain axiom fields as unordered sets (e.g. EquivalentClasses).
This module walks the model_fields metadata to find Unordered() markers and
sorts those fields before serialization. All other fields pass through.
"""

import hashlib
import json
from typing import Final

from pydantic import BaseModel

from ontoloom.ontology.models.axioms import Axiom
from ontoloom.ontology.models.base import ANNOTATIONS_FIELD, TYPE_FIELD
from ontoloom.ontology.models.markers import is_unordered

_SKIP_FIELDS: Final = (TYPE_FIELD, ANNOTATIONS_FIELD)


def _to_sort_key(value):
    if isinstance(value, str):  # StrEnum / IRI
        return value
    if isinstance(value, BaseModel):
        return json.dumps(value.model_dump(), sort_keys=True, separators=(",", ":"))
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _normalize(value):
    if isinstance(value, BaseModel):
        updates = {}
        for name, info in type(value).model_fields.items():
            if name in _SKIP_FIELDS:
                continue
            field_val = getattr(value, name)
            updates[name] = _normalize_field(field_val, info)
        return value.model_copy(update=updates)
    return value


def _normalize_field(value, info):
    if isinstance(value, BaseModel):
        return _normalize(value)
    if isinstance(value, tuple):
        normalized = tuple(_normalize(v) for v in value)
        if is_unordered(info):
            return tuple(sorted(normalized, key=_to_sort_key))
        return normalized
    return value


def canonical_json(axiom: Axiom):
    """Deterministic JSON of an axiom's logical content, excluding annotations."""
    normalized = _normalize(axiom)
    data = normalized.model_dump(exclude={"annotations"})
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def axiom_hash(axiom: Axiom):
    """SHA-256 of the canonical JSON. Stable across annotation changes and operand reordering."""
    return hashlib.sha256(canonical_json(axiom).encode()).hexdigest()
