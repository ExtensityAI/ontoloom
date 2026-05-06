"""Walk an axiom and yield the entity IRIs it references, with kind and position.

Reads EntityType and Position markers from model_fields metadata. Position
propagates downward through recursion; kind applies at the leaf. Declaration is
special-cased because its kind comes from a sibling field's runtime value.
"""

from collections.abc import Iterator

from ontoloom.models import FrozenModel
from ontoloom.owl.axioms import BaseAxiom, Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType, Position, find_marker

# Discriminator field -> skipped by the walker. Annotations are NOT skipped here
# because annotations carry entity IRIs that this walker exists to surface.
_SKIP = ("type",)


type EntityRef = tuple[IRI, EntityType | None, Position | None]


def iter_axiom_entities(axiom: BaseAxiom) -> Iterator[EntityRef]:
    """Yield all entities referenced in an axiom, with their roles and positions."""
    yield from _walk_model(axiom, position=None)


def _walk_model(model: FrozenModel, position: Position | None) -> Iterator[EntityRef]:
    # Declaration's entity kind lives in the entity_type field's runtime value,
    # not in field metadata -> handle before the generic field walk.
    if isinstance(model, Declaration):
        yield model.iri, model.entity_type, Position.ENTITY
        for ann in model.annotations:
            yield from _walk_model(ann, position=None)
        return

    for name, info in type(model).model_fields.items():
        if name in _SKIP:
            continue
        field_pos = find_marker(info, Position) or position  # explicit marker beats inherited
        yield from _walk_value(getattr(model, name), find_marker(info, EntityType), field_pos)


def _walk_value(value, kind: EntityType | None, position: Position | None) -> Iterator[EntityRef]:
    match value:
        case IRI():
            yield value, kind, position
        case tuple():
            # kind is fixed per field, so it stays the same across all elements
            for item in value:
                yield from _walk_value(item, kind, position)
        case FrozenModel():
            # nested model: kind resets -> each of its fields carries its own EntityKind marker
            yield from _walk_model(value, position)
        case str() | int() | float() | bool() | None:
            # non-IRI leaf (StrEnum like DataType/EntityType, LangLiteral text, numeric value, etc.)
            return
        case _:
            msg = f"unhandled value {type(value).__name__} in entity extraction"
            raise TypeError(msg)
