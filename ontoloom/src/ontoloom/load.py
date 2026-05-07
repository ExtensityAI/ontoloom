"""Shared axiom deserialization with corruption detection."""

from pydantic import TypeAdapter, ValidationError

from ontoloom.errors import StoreCorruptionError
from ontoloom.owl.axioms import Axiom

_AXIOM_ADAPTER: TypeAdapter[Axiom] = TypeAdapter(Axiom)


def load_axiom(data: str | bytes, context: str = "") -> Axiom:
    try:
        return _AXIOM_ADAPTER.validate_json(data)
    except (ValidationError, ValueError) as e:
        # ValueError covers our `make_tag_resolver` raise on dispatch failure;
        # Pydantic propagates it unwrapped instead of wrapping it as ValidationError.
        raise StoreCorruptionError(context or "axiom deserialization failed", e) from e
