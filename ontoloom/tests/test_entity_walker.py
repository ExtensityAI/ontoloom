"""Tests for the EntityType peel through tuple/Annotated in `_walk_model`.

When `EntityType` lives on a type alias buried inside `Annotated[..., EntityType.X]`
or inside `tuple[X, ...]` element types, the walker must dig past the outer
type form to find it. Position propagation must remain unchanged.
"""

from typing import Annotated, Literal

from ontoloom.axioms.entity_walker import _walk_model, iter_axiom_entities
from ontoloom.models import FrozenModel
from ontoloom.owl.axioms import EquivalentClasses, ObjectPropertyDomain
from ontoloom.owl.expressions import ObjectSomeValuesFrom
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType, Position

type _ClassIri = Annotated[IRI, EntityType.CLASS]


class _Synthetic(FrozenModel):
    type: Literal["_Synthetic"] = "_Synthetic"
    solo: _ClassIri
    many: tuple[_ClassIri, ...]


def test_peel_finds_entity_type_in_alias_on_solo_field():
    model = _Synthetic(solo=IRI(":A"), many=())
    result = list(_walk_model(model, position=None))
    assert (IRI(":A"), EntityType.CLASS, None) in result


def test_peel_finds_entity_type_in_tuple_element_alias():
    model = _Synthetic(solo=IRI(":A"), many=(IRI(":B"), IRI(":C")))
    result = list(_walk_model(model, position=None))
    kinds = {iri: kind for iri, kind, _ in result}
    assert kinds[IRI(":B")] == EntityType.CLASS
    assert kinds[IRI(":C")] == EntityType.CLASS


# -- Outer marker wins over peeled marker ---------------------------------


type _ObjectPropIri = Annotated[IRI, EntityType.OBJECT_PROPERTY]


class _OuterWins(FrozenModel):
    type: Literal["_OuterWins"] = "_OuterWins"
    # Outer marker says DATA_PROPERTY; alias inside says OBJECT_PROPERTY.
    # Outer must win because `find_marker` returns first.
    iri: Annotated[_ObjectPropIri, EntityType.DATA_PROPERTY]


def test_outer_field_marker_beats_alias_marker():
    model = _OuterWins(iri=IRI(":dp"))
    result = list(_walk_model(model, position=None))
    assert result == [(IRI(":dp"), EntityType.DATA_PROPERTY, None)]


# -- Position is unchanged: regression on real axioms -----------------------


def test_position_unchanged_equivalent_classes_with_restriction():
    """Outer Position.MEMBER on tuple, Position.FILLER inside the nested restriction."""
    ax = EquivalentClasses(
        equivalent_classes=(
            IRI(":Parent"),
            ObjectSomeValuesFrom(property=IRI(":hasChild"), filler=IRI(":Person")),
        )
    )
    entries = list(iter_axiom_entities(ax))

    pos_by_iri = {str(iri): pos for iri, _, pos in entries}
    assert pos_by_iri[":Parent"] == Position.MEMBER
    assert pos_by_iri[":hasChild"] == Position.RESTRICTION_PROPERTY
    assert pos_by_iri[":Person"] == Position.FILLER


def test_position_unchanged_object_property_domain():
    """Domain Position propagates to the bare IRI in domain position."""
    ax = ObjectPropertyDomain(object_property=IRI(":r"), domain=IRI(":C"))
    entries = list(iter_axiom_entities(ax))

    pos_by_iri = {str(iri): pos for iri, _, pos in entries}
    assert pos_by_iri[":r"] == Position.PROPERTY
    assert pos_by_iri[":C"] == Position.DOMAIN
