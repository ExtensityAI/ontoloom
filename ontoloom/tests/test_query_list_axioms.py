"""Tests for the ListAxioms query."""

import json

from ontoloom.axioms.store import add_axioms
from ontoloom.hashing import AxiomHash, HashedAxiom
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import AxiomTag, EntityType
from ontoloom.query.constraints import AlwaysFalse, MentionsAny, WithTypes
from ontoloom.query.list_axioms import ListAxioms

# -- render snapshots --


def test_render_no_constraints_no_pagination():
    compiled = (ListAxioms(constraints=())).render()
    assert compiled.sql == "SELECT a.hash, json(a.data) FROM axioms a WHERE 1 ORDER BY a.hash"
    assert compiled.params == ()


def test_render_with_of_types():
    compiled = (ListAxioms(constraints=(WithTypes(tags=(AxiomTag.DECLARATION,)),))).render()
    assert compiled.sql == (
        "SELECT a.hash, json(a.data) FROM axioms a WHERE a.type IN (?) ORDER BY a.hash"
    )
    assert compiled.params == ("Declaration",)


def test_render_limit_only():
    compiled = (ListAxioms(constraints=(), limit=10)).render()
    assert compiled.sql == (
        "SELECT a.hash, json(a.data) FROM axioms a WHERE 1 ORDER BY a.hash LIMIT ?"
    )
    assert compiled.params == (10,)


def test_render_limit_and_offset():
    compiled = (ListAxioms(constraints=(), limit=10, offset=5)).render()
    assert compiled.sql == (
        "SELECT a.hash, json(a.data) FROM axioms a WHERE 1 ORDER BY a.hash LIMIT ? OFFSET ?"
    )
    assert compiled.params == (10, 5)


def test_render_constraints_and_pagination():
    compiled = (
        ListAxioms(
            constraints=(MentionsAny(iris=(IRI("ex:A"),)),),
            limit=3,
            offset=1,
        )
    ).render()
    assert compiled.sql == (
        "SELECT a.hash, json(a.data) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri IN (?)) "
        "ORDER BY a.hash LIMIT ? OFFSET ?"
    )
    assert compiled.params == ("ex:A", 3, 1)


def test_render_always_false_short_circuits():
    compiled = (ListAxioms(constraints=(AlwaysFalse(),), limit=5)).render()
    assert compiled.sql == (
        "SELECT a.hash, json(a.data) FROM axioms a WHERE 0 ORDER BY a.hash LIMIT ?"
    )
    assert compiled.params == (5,)


def test_render_always_includes_order_by():
    for q in [
        ListAxioms(constraints=()),
        ListAxioms(constraints=(WithTypes(tags=(AxiomTag.DECLARATION,)),)),
        ListAxioms(constraints=(), limit=10),
        ListAxioms(constraints=(), limit=10, offset=5),
        ListAxioms(constraints=(AlwaysFalse(),)),
    ]:
        assert "ORDER BY a.hash" in q.render().sql


# -- _run integration --


def test_run_empty_ontology(s):
    assert (ListAxioms(constraints=()))._run(s) == []


def test_run_returns_hash_and_json(s):
    decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    add_axioms(s, [decl])

    result = (ListAxioms(constraints=()))._run(s)
    assert len(result) == 1
    h, data = result[0]
    assert isinstance(h, AxiomHash)
    assert h == HashedAxiom.of(decl).hash
    assert isinstance(data, str)
    payload = json.loads(data)
    assert payload["entity_type"] == EntityType.CLASS
    assert payload["iri"] == "ex:Dog"


def test_run_lists_in_hash_order(s):
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
    ]
    add_axioms(s, decls)

    result = (ListAxioms(constraints=()))._run(s)
    hashes = [h for h, _ in result]
    assert hashes == sorted(hashes)


def test_run_pagination_stable(s):
    decls = [Declaration(entity_type=EntityType.CLASS, iri=IRI(f"ex:C{i}")) for i in range(6)]
    add_axioms(s, decls)

    page1 = (ListAxioms(constraints=(), limit=2))._run(s)
    page2 = (ListAxioms(constraints=(), limit=2, offset=2))._run(s)

    assert len(page1) == 2
    assert len(page2) == 2
    page1_hashes = [h for h, _ in page1]
    page2_hashes = [h for h, _ in page2]
    assert set(page1_hashes).isdisjoint(page2_hashes)


def test_run_pagination_full_walk(s):
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
    ]
    add_axioms(s, decls)

    full = (ListAxioms(constraints=()))._run(s)
    paged = (
        (ListAxioms(constraints=(), limit=1))._run(s)
        + (ListAxioms(constraints=(), limit=1, offset=1))._run(s)
        + (ListAxioms(constraints=(), limit=1, offset=2))._run(s)
    )
    assert paged == full


def test_run_filter_by_of_types(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
        ],
    )
    result = (ListAxioms(constraints=(WithTypes(tags=(AxiomTag.SUB_CLASS_OF,)),)))._run(s)
    assert len(result) == 1
    _, data = result[0]
    payload = json.loads(data)
    assert payload["sub_class"] == "ex:Dog"


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert (ListAxioms(constraints=(AlwaysFalse(),)))._run(s) == []
