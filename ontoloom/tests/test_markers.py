from typing import Annotated, Literal

from ontoloom.owl.markers import (
    EntityType,
    Position,
    Unordered,
    find_marker,
    is_unordered,
)
from pydantic import BaseModel, ConfigDict


class _M(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["_M"] = "_M"
    members: Annotated[tuple[str, ...], Unordered()]
    iri: Annotated[str, EntityType.CLASS, Position.SUB_CLASS]
    plain: str


def test_is_unordered_true_for_marked_field():
    assert is_unordered(_M.model_fields["members"]) is True


def test_is_unordered_false_for_unmarked_field():
    assert is_unordered(_M.model_fields["plain"]) is False


def test_find_marker_returns_entity_type():
    assert find_marker(_M.model_fields["iri"], EntityType) == EntityType.CLASS


def test_find_marker_none_when_absent():
    assert find_marker(_M.model_fields["plain"], EntityType) is None


def test_find_marker_returns_position():
    assert find_marker(_M.model_fields["iri"], Position) == Position.SUB_CLASS


def test_unordered_equality():
    assert Unordered() == Unordered()


def test_axiom_tag_classmethod():
    """tag() classmethod returns the class name."""
    from ontoloom.owl.axioms import Declaration, SubClassOf

    assert Declaration.tag() == "Declaration"
    assert SubClassOf.tag() == "SubClassOf"
