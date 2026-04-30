"""Canonical normalization and content hashing for OWL 2 axioms.

OWL 2 treats certain axiom fields as unordered sets (e.g. EquivalentClasses).
This module walks the model_fields metadata to find Unordered() markers and
sorts those fields before serialization. All other fields pass through.
"""

import hashlib
import json
from collections.abc import Sequence

from pydantic import BaseModel

from ontoloom.ontology.models.base import WALKER_SKIP, BaseAxiom
from ontoloom.ontology.models.markers import is_unordered

# Display width for hash prefixes shown to agents/users. 12 hex chars = 48 bits =
# 2.8e14 distinct values; collision probability stays under 0.02% even at 10M
# axioms (SNOMED CT scale). Input resolution still accepts any unambiguous
# prefix, but every successful display path uses this width for stability.
HASH_DISPLAY_LEN = 12  # A: no reason for this huge comment, add a docstring that explains what it means, not what could happen


def _to_sort_key(value):  # A: what does this func do? add docstring
    if isinstance(value, str):  # StrEnum / IRI
        return value
    if isinstance(value, BaseModel):
        return json.dumps(value.model_dump(), sort_keys=True, separators=(",", ":"))
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _normalize_model[T: BaseModel](model: T) -> T:
    # A: do we really need BaseModel here? I think we can narrow that!!! also docstring
    # A global: I think we should add docstrings for most functions (mentioned before). they should explain what the func does, what args are, what the funcs can raise, adhere to best practices, not talk about impl details and all, and for small funcs we can leave out params and all and just a single line expl, so keep the mconcise in general, general python coding rule please so add to your rules file
    updates = {}
    for name, info in type(model).model_fields.items():
        if name in WALKER_SKIP:
            continue
        updates[name] = _normalize_field(getattr(model, name), info)
    # A global: leftover comment, this is a design decision in code that does not really matter, so please check if some like these below are left anywhere else and fix
    # Pydantic v2 model_copy has no `validate` kwarg. Safe today: Unordered
    # tuples are only sorted (length and element types preserved), so
    # Field(min_length=...) cannot newly fail. If normalization ever filters
    # values, swap to `type(model).model_validate(updated.model_dump())`.
    return model.model_copy(update=updates)


def _normalize_field(value, info):
    if isinstance(value, tuple):
        normalized = tuple(_normalize_value(v) for v in value)
        if is_unordered(info):
            return tuple(sorted(normalized, key=_to_sort_key))
        return normalized
    return _normalize_value(value)


def _normalize_value(value):
    match value:
        case BaseModel():
            return _normalize_model(value)
        case str() | int() | float() | None:
            return value
        case _:
            msg = f"unhandled value {type(value).__name__} in canonical normalization"
            raise TypeError(msg)


def canonical_json(axiom: BaseAxiom):
    """Deterministic JSON of an axiom's logical content, excluding annotations."""
    normalized = _normalize_model(axiom)
    data = normalized.model_dump(exclude={"annotations"})
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def axiom_hash(axiom: BaseAxiom):
    """SHA-256 of the canonical JSON. Stable across annotation changes and operand reordering."""
    return hashlib.sha256(canonical_json(axiom).encode()).hexdigest()


def truncate_hash(h: str) -> str:
    """Return the standard display prefix of a hash."""
    return h[:HASH_DISPLAY_LEN]


def min_distinguishing_prefixes(hashes: Sequence[str]) -> list[str]:
    """For a set of hashes, return the shortest prefix of each that doesn't share
    its leading characters with any other in the set. Used by AmbiguousHashError
    to tell the caller exactly how much they need to extend their prefix.

    Returns prefixes in the original order of the input.
    """
    if len(hashes) == 1:
        return [hashes[0]]
    indexed = sorted(enumerate(hashes), key=lambda p: p[1])
    out: list[str] = [""] * len(hashes)
    for rank, (orig_idx, h) in enumerate(indexed):
        lcp = 0
        if rank > 0:
            lcp = max(lcp, _lcp_len(h, indexed[rank - 1][1]))
        if rank < len(indexed) - 1:
            lcp = max(lcp, _lcp_len(h, indexed[rank + 1][1]))
        out[orig_idx] = h[: lcp + 1]
    return out


def _lcp_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            return n
        n += 1
    return n
