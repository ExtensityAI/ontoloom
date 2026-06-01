"""Search-related tests not covered by test_search_smoke.py.

Smoke tests cover search-by-text, role, namespace, pagination, and tiebreakers.
This file covers LIKE-escape safety and entity_text cleanup on partial axiom
removal.
"""

from ontoloom.axioms.mutations import add_axioms, remove_by_hash
from ontoloom.entities.reader import find_entities
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes.types import PrefixName


def test_entity_text_survives_partial_removal(s):
    """Removing one axiom that mentions an entity must not break search for that entity
    if other axioms still reference it."""
    ax1 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    ax2 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    result = add_axioms(s, [ax1, ax2])

    # Remove the SubClassOf but keep the Declaration
    subclassof_hash = next(ha.hash for ha in result.added if ha.axiom.tag() == "SubClassOf")
    remove_by_hash(s, [subclassof_hash])

    # ex:Dog should still be searchable (Declaration still references it)
    iris = find_entities(s, query="Dog")
    assert IRI("ex:Dog") in iris


def test_search_with_like_wildcards(s):
    """Search queries containing % and _ should match literally, not as wildcards."""
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Rate100Percent")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Rate100Points")),
        ],
    )
    # "100%" should NOT match "100Points" -> the % must be literal
    iris = find_entities(s, query="100%")
    for iri in iris:
        assert "100%" in str(iri) or "100%" in iri.local_name


def test_namespace_filter_escapes_underscore(s):
    """Underscore in a prefix must be matched literally, not as SQL LIKE wildcard."""
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("a_b:X")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("aXb:Y")),
        ],
    )
    iris = find_entities(s, namespace=PrefixName("a_b"))
    # Without ESCAPE, `a_b:%` would match `aXb:Y` because `_` is a LIKE wildcard.
    assert IRI("a_b:X") in iris
    assert IRI("aXb:Y") not in iris
