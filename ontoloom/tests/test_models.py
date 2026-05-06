"""Tests for models.py helpers."""

from ontoloom.models import tagged_union_meta
from pydantic import Discriminator
from pydantic.fields import FieldInfo


def test_tagged_union_meta_defaults():
    """Test that no-arg call and explicit defaults produce identical metadata."""
    # No args (current form)
    disc1, field1 = tagged_union_meta()

    # Explicit defaults
    disc2, field2 = tagged_union_meta("type", "object")

    # Assert Discriminator equivalence
    assert isinstance(disc1, Discriminator)
    assert isinstance(disc2, Discriminator)
    assert disc1.discriminator == disc2.discriminator
    assert disc1.discriminator == "type"

    # Assert Field equivalence
    assert isinstance(field1, FieldInfo)
    assert isinstance(field2, FieldInfo)
    assert field1.json_schema_extra == field2.json_schema_extra
    assert field1.json_schema_extra == {"type": "object"}


def test_tagged_union_meta_callable_discriminator_and_array_type():
    """Test callable discriminator and array type parameter."""

    def custom_disc(v: object) -> str:
        if isinstance(v, str):
            return "iri"
        if isinstance(v, dict):
            return v.get("type", "")
        return getattr(v, "type", "")

    disc, field = tagged_union_meta(custom_disc, ["string", "object"])

    # Assert Discriminator uses the callable
    assert isinstance(disc, Discriminator)
    assert disc.discriminator is custom_disc

    # Assert Field has array type
    assert isinstance(field, FieldInfo)
    assert field.json_schema_extra is not None
    assert isinstance(field.json_schema_extra, dict)
    assert field.json_schema_extra["type"] == ["string", "object"]
