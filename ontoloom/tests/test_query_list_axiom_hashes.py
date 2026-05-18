"""Tests for the ListAxiomHashes query."""

from ontoloom.axioms.store import add_axioms
from ontoloom.hashing import AxiomHash, HashedAxiom
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import AxiomTag, EntityType
from ontoloom.query.constraints import AlwaysFalse, MentionsAny, WithTypes
from ontoloom.query.list_axiom_hashes import ListAxiomHashes

# -- render snapshots --


def test_render_no_constraints_no_pagination():
    compiled = (ListAxiomHashes(constraints=())).render()
    assert compiled.sql == "SELECT a.hash FROM axioms a WHERE 1 ORDER BY a.hash"
    assert compiled.params == ()


def test_render_with_of_types():
    compiled = (ListAxiomHashes(constraints=(WithTypes(tags=(AxiomTag.DECLARATION,)),))).render()
    assert compiled.sql == ("SELECT a.hash FROM axioms a WHERE a.type IN (?) ORDER BY a.hash")
    assert compiled.params == ("Declaration",)


def test_render_limit_only():
    compiled = (ListAxiomHashes(constraints=(), limit=10)).render()
    assert compiled.sql == "SELECT a.hash FROM axioms a WHERE 1 ORDER BY a.hash LIMIT ?"
    assert compiled.params == (10,)


def test_render_limit_and_offset():
    compiled = (ListAxiomHashes(constraints=(), limit=10, offset=5)).render()
    assert compiled.sql == "SELECT a.hash FROM axioms a WHERE 1 ORDER BY a.hash LIMIT ? OFFSET ?"
    assert compiled.params == (10, 5)


def test_render_limit_with_zero_offset_omits_offset_clause():
    compiled = (ListAxiomHashes(constraints=(), limit=10, offset=0)).render()
    assert compiled.sql == "SELECT a.hash FROM axioms a WHERE 1 ORDER BY a.hash LIMIT ?"
    assert compiled.params == (10,)


def test_render_constraints_and_pagination():
    compiled = (
        ListAxiomHashes(
            constraints=(MentionsAny(iris=(IRI("ex:A"),)),),
            limit=3,
            offset=1,
        )
    ).render()
    assert compiled.sql == (
        "SELECT a.hash FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri IN (?)) "
        "ORDER BY a.hash LIMIT ? OFFSET ?"
    )
    assert compiled.params == ("ex:A", 3, 1)


def test_render_always_false_short_circuits():
    compiled = (ListAxiomHashes(constraints=(AlwaysFalse(),), limit=5)).render()
    assert compiled.sql == "SELECT a.hash FROM axioms a WHERE 0 ORDER BY a.hash LIMIT ?"
    assert compiled.params == (5,)


def test_render_always_includes_order_by():
    for q in [
        ListAxiomHashes(constraints=()),
        ListAxiomHashes(constraints=(WithTypes(tags=(AxiomTag.DECLARATION,)),)),
        ListAxiomHashes(constraints=(), limit=10),
        ListAxiomHashes(constraints=(), limit=10, offset=5),
        ListAxiomHashes(constraints=(AlwaysFalse(),)),
    ]:
        assert "ORDER BY a.hash" in q.render().sql


# -- _run integration --


def test_run_empty_ontology(s):
    assert (ListAxiomHashes(constraints=()))._run(s) == []


def test_run_lists_in_hash_order(s):
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
    ]
    add_axioms(s, decls)

    result = (ListAxiomHashes(constraints=()))._run(s)
    expected = sorted([HashedAxiom.of(d).hash for d in decls])
    assert result == expected


def test_run_returns_axiom_hash_typed_values(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = (ListAxiomHashes(constraints=()))._run(s)
    assert len(result) == 1
    assert isinstance(result[0], AxiomHash)


def test_run_pagination_stable(s):
    decls = [Declaration(entity_type=EntityType.CLASS, iri=IRI(f"ex:C{i}")) for i in range(6)]
    add_axioms(s, decls)

    page1 = (ListAxiomHashes(constraints=(), limit=2))._run(s)
    page2 = (ListAxiomHashes(constraints=(), limit=2, offset=2))._run(s)

    assert len(page1) == 2
    assert len(page2) == 2
    assert set(page1).isdisjoint(page2)


def test_run_pagination_full_walk(s):
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
    ]
    add_axioms(s, decls)

    full = (ListAxiomHashes(constraints=()))._run(s)
    paged = (
        (ListAxiomHashes(constraints=(), limit=1))._run(s)
        + (ListAxiomHashes(constraints=(), limit=1, offset=1))._run(s)
        + (ListAxiomHashes(constraints=(), limit=1, offset=2))._run(s)
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
    result = (ListAxiomHashes(constraints=(WithTypes(tags=(AxiomTag.SUB_CLASS_OF,)),)))._run(s)
    expected_hash = HashedAxiom.of(
        SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    ).hash
    assert result == [expected_hash]


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert (ListAxiomHashes(constraints=(AlwaysFalse(),)))._run(s) == []
