"""Shared axiom deserialization with corruption detection."""

from pydantic import TypeAdapter, ValidationError

from ontoloom.errors import StoreCorruptionError
from ontoloom.models import UnionDispatchError
from ontoloom.owl.axioms import Axiom

_AXIOM_ADAPTER: TypeAdapter[Axiom] = TypeAdapter(Axiom)


def load_axiom(data: str | bytes):
    try:
        return _AXIOM_ADAPTER.validate_json(data)
    except (ValidationError, UnionDispatchError) as e:
        # UnionDispatchError is what `make_tag_resolver` raises on dispatch
        # failure; Pydantic propagates it unwrapped (only ValueError /
        # AssertionError get wrapped as ValidationError).
        msg = "axiom deserialization failed"
        raise StoreCorruptionError(msg, e) from e
