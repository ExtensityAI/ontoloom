from typing import Annotated, Literal

from ontoloom.ontology.models.base import EntityType
from ontoloom.ontology.models.markers import (
    EntityKind,
    EntityPosition,
    Unordered,
    get_entity_kind,
    get_entity_position,
    is_unordered,
)
from ontoloom.ontology.types import Position
from pydantic import BaseModel, ConfigDict


class _M(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["_M"] = "_M"
    members: Annotated[tuple[str, ...], Unordered()]
    iri: Annotated[str, EntityKind(EntityType.CLASS), EntityPosition(Position.SUB_CLASS)]
    plain: str


def test_is_unordered_true_for_marked_field():
    assert is_unordered(_M.model_fields["members"]) is True


def test_is_unordered_false_for_unmarked_field():
    assert is_unordered(_M.model_fields["plain"]) is False


def test_get_entity_kind_returns_kind():
    assert get_entity_kind(_M.model_fields["iri"]) == EntityType.CLASS


def test_get_entity_kind_none_when_absent():
    assert get_entity_kind(_M.model_fields["plain"]) is None


def test_get_entity_position_returns_position():
    assert get_entity_position(_M.model_fields["iri"]) == Position.SUB_CLASS


def test_marker_equality_via_dataclass():
    assert EntityKind(EntityType.CLASS) == EntityKind(EntityType.CLASS)
    assert Unordered() == Unordered()
