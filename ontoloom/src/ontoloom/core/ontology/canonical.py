"""Canonical normalization and content hashing for OWL 2 axioms.

Axiom identity is a SHA-256 hash of canonical JSON. The canonical form:
- Excludes the ``annotations`` field (annotations are metadata, not logic)
- Sorts set-semantic fields (where operand order is irrelevant in OWL 2)
- Uses compact, deterministic JSON serialization

Set-semantic fields (order irrelevant in OWL 2):
    EquivalentClasses.expressions, DisjointClasses.expressions,
    EquivalentObjectProperties.properties, EquivalentDataProperties.properties,
    SameIndividual.individuals, DifferentIndividuals.individuals,
    HasKey.object_properties, HasKey.data_properties,
    ObjectIntersectionOf.operands, DataIntersectionOf.operands
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ontoloom.core.ontology.models.axioms import Axiom

_SET_SEMANTIC_KEYS = frozenset(
    {
        "expressions",
        "properties",
        "individuals",
        "object_properties",
        "data_properties",
        "operands",
    }
)


def _normalize(value: Any, key: str | None = None) -> Any:
    """Recursively normalize a value for canonical ordering.

    Sorts sequence values whose parent key is in ``_SET_SEMANTIC_KEYS``.
    """
    if isinstance(value, dict):
        return {k: _normalize(v, key=k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        normalized = [_normalize(item) for item in value]
        if key in _SET_SEMANTIC_KEYS:
            normalized = sorted(
                normalized,
                key=lambda x: (
                    json.dumps(x, sort_keys=True, separators=(",", ":"))
                    if isinstance(x, dict)
                    else json.dumps(x)
                ),
            )
        return normalized
    return value


def canonical_dump(axiom: Axiom) -> str:
    """Return deterministic JSON of an axiom's logical content.

    Excludes ``annotations``. Sorts set-semantic fields.
    """
    data = axiom.model_dump(exclude={"annotations"})
    data = _normalize(data)
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def content_hash(axiom: Axiom) -> str:
    """SHA-256 hex digest of the axiom's canonical logical content."""
    return hashlib.sha256(canonical_dump(axiom).encode()).hexdigest()
