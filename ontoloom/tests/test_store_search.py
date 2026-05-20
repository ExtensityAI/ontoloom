"""Search-related store tests not covered by test_search_smoke.py.

Smoke tests cover search-by-text, role, namespace, pagination, and tiebreakers.
This file covers store-level invariants: LIKE-escape safety and entity_text
cleanup on partial axiom removal.
"""

from ontoloom.axioms.store import add_axioms, remove_by_hash
from ontoloom.entities.store import collect_entity_iris, search_entities
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType


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
    page = search_entities(s, query="Dog", limit=10)
    iris = [m.iri for m in page.matches]
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
    page = search_entities(s, query="100%", limit=10)
    for m in page.matches:
        assert "100%" in str(m.iri) or "100%" in m.iri.local_name


def test_namespace_filter_escapes_underscore(s):
    """Underscore in a prefix must be matched literally, not as SQL LIKE wildcard."""
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("a_b:X")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("aXb:Y")),
        ],
    )
    iris = collect_entity_iris(s, namespace="a_b")
    # Without ESCAPE, `a_b:%` would match `aXb:Y` because `_` is a LIKE wildcard.
    assert "a_b:X" in iris
    assert "aXb:Y" not in iris
