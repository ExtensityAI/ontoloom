"""Shared fixtures for the ontoloom core test suite.

`add_axioms`, `replace_axiom`, and `rename_iri` validate prefix declarations
at the core level. Tests that add axioms therefore need the prefixes they use
declared first; the `s` fixture handles that for the common test set. The
`bare_session` fixture is for tests that exercise the prefix-management API
itself and need to start from a clean prefix table.
"""

import pytest
from ontoloom.connection import Ontology, session
from ontoloom.prefixes.store import set_prefix

_TEST_PREFIXES = {
    "ex": "http://example.org/",
    "other": "http://other.org/",
    "bio": "http://bio.org/",
    "ns": "http://ns.example/",
    "my_ont": "http://myont.example/",
    "a_b": "http://a-b.example/",
    "aXb": "http://a-x-b.example/",
    "prefix": "http://prefix.example/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
}


@pytest.fixture()
def bare_session(tmp_path):
    """Fresh ontology, no prefixes declared. For prefix-management tests."""
    path = tmp_path / "test.ontology.db"
    Ontology.create(path)
    with session(Ontology(path)) as s:
        yield s
        s.commit()


@pytest.fixture()
def s(bare_session):
    """Session with the standard test prefixes pre-declared."""
    for name, iri in _TEST_PREFIXES.items():
        set_prefix(bare_session, name, iri)
    return bare_session
