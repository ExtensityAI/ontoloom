"""IRI parser validation. Pure: no DB, no fixtures."""

import pytest
from ontoloom.owl.iri import IRI


def test_iri_valid_cases():
    assert IRI(":Dog") == ":Dog"
    assert IRI("owl:Thing") == "owl:Thing"
    assert IRI("ex:a:b") == "ex:a:b"  # colon in local name is fine
    assert IRI("my_ont:Foo") == "my_ont:Foo"  # underscore in prefix


def test_iri_rejects_empty():
    with pytest.raises(ValueError, match="prefix:local_name"):
        IRI("")


def test_iri_rejects_no_colon():
    with pytest.raises(ValueError, match="prefix:local_name"):
        IRI("nocolon")


def test_iri_rejects_empty_local_name():
    with pytest.raises(ValueError, match="prefix:local_name"):
        IRI("prefix:")


def test_iri_rejects_control_chars():
    with pytest.raises(ValueError):
        IRI("ex:foo\nbar")
    with pytest.raises(ValueError):
        IRI("ex:foo\x00bar")


def test_iri_rejects_whitespace_in_local_name():
    with pytest.raises(ValueError, match="prefix:local_name"):
        IRI("ex:foo bar")
    with pytest.raises(ValueError, match="prefix:local_name"):
        IRI("ex:foo\tbar")


def test_iri_rejects_invalid_prefix():
    with pytest.raises(ValueError):
        IRI("1bad:foo")  # starts with digit
    with pytest.raises(ValueError):
        IRI("a%b:foo")  # % in prefix
