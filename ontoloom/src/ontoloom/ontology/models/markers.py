"""Field-level metadata markers for OWL axiom declarations.

Three single-purpose markers declare OWL-domain facts about Pydantic fields.
Read by canonical normalization, entity extraction, pattern matching, and codegen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic.fields import FieldInfo

if TYPE_CHECKING:
    from ontoloom.ontology.models.literals import EntityType, Position, StoredPosition


@dataclass(frozen=True, slots=True)
class Unordered:
    """The field is a tuple whose order has no semantic meaning in OWL.

    Read by canonical normalization (sorts), pattern matching (permutes),
    and pattern codegen (allows partial-set Contains in generated patterns).
    """


@dataclass(frozen=True, slots=True)
class EntityKind:
    """The IRI value at this field references an OWL entity of this kind.

    Intrinsic to the leaf (e.g. NamedClass.iri is always a Class IRI).
    """

    kind: EntityType


@dataclass(frozen=True, slots=True)
class EntityPosition:
    """Values flowing through this field play this structural role in the axiom.

    Contextual: the parent's field declaration sets it; the extraction walker
    propagates it downward into nested expressions. `Position.ANY` is rejected
    statically: it's a query-time filter, not a stored or extracted role.
    """

    position: StoredPosition


def is_unordered(info: FieldInfo) -> bool:
    return any(isinstance(m, Unordered) for m in info.metadata)


def get_entity_kind(info: FieldInfo) -> EntityType | None:
    for m in info.metadata:
        if isinstance(m, EntityKind):
            return m.kind
    return None


def get_entity_position(info: FieldInfo) -> Position | None:
    for m in info.metadata:
        if isinstance(m, EntityPosition):
            return m.position
    return None
