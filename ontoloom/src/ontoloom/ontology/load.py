"""Shared axiom deserialization with corruption detection."""

from pydantic import TypeAdapter, ValidationError

from ontoloom.ontology.errors import StoreCorruptionError
from ontoloom.ontology.models.axioms import Axiom

_AXIOM_ADAPTER: TypeAdapter[Axiom] = TypeAdapter(Axiom)


def load_axiom(data: str | bytes, context: str = "") -> Axiom:
    try:
        return _AXIOM_ADAPTER.validate_json(data)
    except ValidationError as e:
        raise StoreCorruptionError(context or "axiom deserialization failed", e) from e
