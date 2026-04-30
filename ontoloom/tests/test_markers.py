from typing import Annotated, Literal

from ontoloom.ontology.models.literals import EntityType, Position
from ontoloom.ontology.models.markers import (
    EntityKind,
    EntityPosition,
    Unordered,
    get_entity_kind,
    get_entity_position,
    is_unordered,
)
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


def test_tagged_model_type_classvar():
    """type_ ClassVar resolves to the Literal default of the type field."""
    from ontoloom.ontology.models.axioms import Declaration, SubClassOf

    assert Declaration.type_ == "Declaration"
    assert SubClassOf.type_ == "SubClassOf"


def test_tagged_model_rejects_missing_default():
    """A TaggedModel subclass that declares `type` without a str default raises."""
    import pytest
    from ontoloom.ontology.models._pydantic import TaggedModel

    with pytest.raises(TypeError, match="must be Literal"):

        class _Bad(TaggedModel):
            type: str  # no default — invalid


def test_type_field_constants():
    from ontoloom.ontology.models.base import ANNOTATIONS_FIELD, TYPE_FIELD

    assert TYPE_FIELD == "type"
    assert ANNOTATIONS_FIELD == "annotations"
