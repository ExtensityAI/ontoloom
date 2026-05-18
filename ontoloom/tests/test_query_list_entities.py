"""Tests for the ListEntities query."""

from ontoloom.axioms.store import add_axioms
from ontoloom.owl.axioms import Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query.constraints import AlwaysFalse, InIRIs, WithRoles
from ontoloom.query.list_entities import ListEntities

# -- render snapshots: no DB --


def test_render_no_constraints_no_pagination():
    compiled = (ListEntities(constraints=())).render()
    assert compiled.sql == (
        "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae WHERE 1 ORDER BY ae.entity_iri"
    )
    assert compiled.params == ()


def test_render_with_iris():
    compiled = (ListEntities(constraints=(InIRIs(iris=(IRI("ex:B"), IRI("ex:A"))),))).render()
    assert compiled.sql == (
        "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
        "WHERE ae.entity_iri IN (?,?) "
        "ORDER BY ae.entity_iri"
    )
    assert compiled.params == ("ex:A", "ex:B")


def test_render_limit_only():
    compiled = (ListEntities(constraints=(), limit=10)).render()
    assert compiled.sql == (
        "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae WHERE 1 ORDER BY ae.entity_iri LIMIT ?"
    )
    assert compiled.params == (10,)


def test_render_limit_and_offset():
    compiled = (ListEntities(constraints=(), limit=10, offset=5)).render()
    assert compiled.sql == (
        "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
        "WHERE 1 "
        "ORDER BY ae.entity_iri "
        "LIMIT ? OFFSET ?"
    )
    assert compiled.params == (10, 5)


def test_render_limit_with_zero_offset_omits_offset_clause():
    compiled = (ListEntities(constraints=(), limit=10, offset=0)).render()
    assert compiled.sql == (
        "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae WHERE 1 ORDER BY ae.entity_iri LIMIT ?"
    )
    assert compiled.params == (10,)


def test_render_constraints_and_pagination():
    compiled = (
        ListEntities(
            constraints=(WithRoles(roles=(EntityType.CLASS,)),),
            limit=3,
            offset=1,
        )
    ).render()
    assert compiled.sql == (
        "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
        "WHERE ae.role IN (?) "
        "ORDER BY ae.entity_iri "
        "LIMIT ? OFFSET ?"
    )
    assert compiled.params == (EntityType.CLASS, 3, 1)


def test_render_always_false_short_circuits():
    compiled = (ListEntities(constraints=(AlwaysFalse(),), limit=5)).render()
    assert compiled.sql == (
        "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
        "WHERE 0 "
        "ORDER BY ae.entity_iri "
        "LIMIT ?"
    )
    assert compiled.params == (5,)


def test_render_always_includes_order_by():
    # ORDER BY ae.entity_iri appears in every variant we emit.
    for q in [
        ListEntities(constraints=()),
        ListEntities(constraints=(InIRIs(iris=(IRI("ex:A"),)),)),
        ListEntities(constraints=(), limit=10),
        ListEntities(constraints=(), limit=10, offset=5),
        ListEntities(constraints=(AlwaysFalse(),)),
    ]:
        assert "ORDER BY ae.entity_iri" in q.render().sql


# -- _run integration --


def test_run_empty_ontology(s):
    assert (ListEntities(constraints=()))._run(s) == []


def test_run_lists_in_iri_order(s):
    # Insert out-of-order; results must come back sorted.
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
        ],
    )
    result = (ListEntities(constraints=()))._run(s)
    assert result == [IRI("ex:Antelope"), IRI("ex:Mongoose"), IRI("ex:Zebra")]


def test_run_pagination_stable(s):
    # Six entities; verify page1 + page2 cover the first 4 with no overlap.
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:D")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:E")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:F")),
        ],
    )

    page1 = (ListEntities(constraints=(), limit=2))._run(s)
    page2 = (ListEntities(constraints=(), limit=2, offset=2))._run(s)

    assert page1 == [IRI("ex:A"), IRI("ex:B")]
    assert page2 == [IRI("ex:C"), IRI("ex:D")]
    assert set(page1).isdisjoint(page2)


def test_run_pagination_full_walk(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
        ],
    )

    full = (ListEntities(constraints=()))._run(s)
    paged = (
        (ListEntities(constraints=(), limit=1))._run(s)
        + (ListEntities(constraints=(), limit=1, offset=1))._run(s)
        + (ListEntities(constraints=(), limit=1, offset=2))._run(s)
    )
    assert paged == full


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert (ListEntities(constraints=(AlwaysFalse(),)))._run(s) == []


def test_run_returns_iri_typed_values(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = (ListEntities(constraints=()))._run(s)
    assert len(result) == 1
    assert isinstance(result[0], IRI)
