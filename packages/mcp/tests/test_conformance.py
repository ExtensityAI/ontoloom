"""Conformance guard for the seven selection-write sites.

Every tool that writes a selection must emit a canonical saved-line of the
form `Saved <N> (axiom|axioms|entity|entities) to "<name>".`, optionally
followed by a parenthetical (`(truncated at limit=...)`), an overwrite tail
(`Replaced previous (N items).`), or a domain clause (e.g. `N duplicate
... values:`).

The four block-with-preview sites (`create_selection`, `search_axioms`,
`search_entities`, `match_axioms`) start their output with the saved-line.
The three embedded-saved-line sites (`get_entity` with `into=`, `rename_iri`
with `into=`, `find_duplicate_entities`) emit the saved-line after an
inspect/diff/group body. This module asserts every site renders a
canonically-shaped saved-line at the expected position, so a future site
cannot re-grow a bespoke saved-line by accident.
"""

import re

import pytest
from ontoloom.connection import Ontology
from ontoloom.owl.axioms import AnnotationAssertion, Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.patterns.types import SubClassOfPattern
from ontoloom.prefixes.types import NamespaceIRI, PrefixName
from ontoloom.selections.types import SelectionName
from ontoloom_mcp.tools.axioms.add_axioms import add_axioms
from ontoloom_mcp.tools.axioms.match_axioms import match_axioms
from ontoloom_mcp.tools.axioms.rename_iri import rename_iri
from ontoloom_mcp.tools.axioms.search_axioms import search_axioms
from ontoloom_mcp.tools.entities.find_duplicate_entities import find_duplicate_entities
from ontoloom_mcp.tools.entities.get_entity import get_entity
from ontoloom_mcp.tools.entities.search_entities import search_entities
from ontoloom_mcp.tools.prefixes.set_prefix import set_prefix
from ontoloom_mcp.tools.selections.create_selection import create_selection

# Canonical saved-line: `Saved <N> (axiom|axioms|entity|entities) to "<name>".`
# Anything after the closing period (truncation parenthetical, overwrite tail,
# domain clause) is tail content and is left unconstrained by this guard.
SAVED_LINE = re.compile(r'^Saved \d+ (axiom|axioms|entity|entities) to "[^"]+"\.')


@pytest.fixture()
def ont(tmp_path):
    path = tmp_path / "conformance.ontology.db"
    Ontology.create(path)
    set_prefix(path=path, name=PrefixName("ex"), iri=NamespaceIRI("http://example.org/"))
    add_axioms(
        path=path,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Canine")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Dog"),
                value=LangLiteral(value="Dog"),
            ),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Canine"),
                value=LangLiteral(value="Dog"),
            ),
        ],
    )
    # Pre-existing entity selection: lets create_selection compose against
    # a known leaf, and find_duplicate_entities can restrict via within=.
    search_entities(path=path, into=SelectionName("all_ents"), namespace=PrefixName("ex"))
    return path


def _assert_starts_with_saved_line(output: str):
    first = output.split("\n", 1)[0]
    assert SAVED_LINE.match(first), f"first line is not a canonical saved-line: {first!r}"


def _assert_contains_saved_line(output: str):
    for line in output.splitlines():
        if SAVED_LINE.match(line):
            return
    msg = f"no canonical saved-line found in output: {output!r}"
    raise AssertionError(msg)


# -- Block-with-preview sites: output starts with the saved-line. --


def test_create_selection_starts_with_saved_line(ont):
    out = create_selection(
        path=ont,
        name=SelectionName("derived"),
        expr=SelectionName("all_ents"),
    )
    _assert_starts_with_saved_line(out)


def test_search_axioms_starts_with_saved_line(ont):
    out = search_axioms(
        path=ont,
        into=SelectionName("labels"),
        query="Dog",
    )
    _assert_starts_with_saved_line(out)


def test_search_entities_starts_with_saved_line(ont):
    out = search_entities(
        path=ont,
        into=SelectionName("dogs"),
        query="Dog",
    )
    _assert_starts_with_saved_line(out)


def test_match_axioms_starts_with_saved_line(ont):
    out = match_axioms(
        path=ont,
        pattern=SubClassOfPattern(sub_class="?x", super_class="?y"),
        into=SelectionName("subclass_matches"),
    )
    _assert_starts_with_saved_line(out)


# -- Embedded-saved-line sites: output contains the saved-line after a body. --


def test_get_entity_with_into_contains_saved_line(ont):
    out = get_entity(
        path=ont,
        iri=IRI("ex:Dog"),
        into=SelectionName("dog_axioms"),
    )
    # Inspect block first, saved-line after.
    assert out.startswith("ex:Dog")
    _assert_contains_saved_line(out)


def test_rename_iri_with_into_contains_saved_line(ont):
    out = rename_iri(
        path=ont,
        old_iri=IRI("ex:Dog"),
        new_iri=IRI("ex:Puppy"),
        into=SelectionName("renamed"),
    )
    # Diff body first, saved-line after.
    assert out.startswith("Renamed ex:Dog -> ex:Puppy")
    _assert_contains_saved_line(out)


def test_find_duplicate_entities_contains_saved_line(ont):
    # Two entities share an rdfs:label value in the fixture, so the populated
    # form (saved-line + domain clause + group body) is exercised.
    out = find_duplicate_entities(
        path=ont,
        into=SelectionName("dup_labels"),
        annotation_property=IRI("rdfs:label"),
    )
    _assert_contains_saved_line(out)
