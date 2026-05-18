"""Tests for the StreamAxioms query."""

import json

from ontoloom.axioms.store import add_axioms
from ontoloom.hashing import AxiomHash, HashedAxiom
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import AxiomTag, EntityType
from ontoloom.query.constraints import AlwaysFalse, MentionsAny, WithTypes
from ontoloom.query.stream_axioms import StreamAxioms

# -- render snapshots --


def test_render_no_constraints():
    compiled = (StreamAxioms(constraints=())).render()
    assert compiled.sql == "SELECT a.hash, json(a.data) FROM axioms a WHERE 1 ORDER BY a.hash"
    assert compiled.params == ()


def test_render_with_of_types():
    compiled = (StreamAxioms(constraints=(WithTypes(tags=(AxiomTag.DECLARATION,)),))).render()
    assert compiled.sql == (
        "SELECT a.hash, json(a.data) FROM axioms a WHERE a.type IN (?) ORDER BY a.hash"
    )
    assert compiled.params == ("Declaration",)


def test_render_with_mentions_any():
    compiled = (StreamAxioms(constraints=(MentionsAny(iris=(IRI("ex:A"),)),))).render()
    assert compiled.sql == (
        "SELECT a.hash, json(a.data) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri IN (?)) "
        "ORDER BY a.hash"
    )
    assert compiled.params == ("ex:A",)


def test_render_always_false():
    compiled = (StreamAxioms(constraints=(AlwaysFalse(),))).render()
    assert compiled.sql == "SELECT a.hash, json(a.data) FROM axioms a WHERE 0 ORDER BY a.hash"
    assert compiled.params == ()


def test_render_always_includes_order_by():
    for q in [
        StreamAxioms(constraints=()),
        StreamAxioms(constraints=(WithTypes(tags=(AxiomTag.DECLARATION,)),)),
        StreamAxioms(constraints=(AlwaysFalse(),)),
    ]:
        assert "ORDER BY a.hash" in q.render().sql


def test_render_no_pagination_clause():
    # Stream queries never emit LIMIT/OFFSET — the caller controls iteration.
    for q in [
        StreamAxioms(constraints=()),
        StreamAxioms(constraints=(WithTypes(tags=(AxiomTag.DECLARATION,)),)),
    ]:
        sql = q.render().sql
        assert "LIMIT" not in sql
        assert "OFFSET" not in sql


# -- _run integration --


def test_run_empty_ontology(s):
    with (StreamAxioms(constraints=()))._run(s) as it:
        assert list(it) == []


def test_run_yields_hash_and_json(s):
    decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    add_axioms(s, [decl])

    with (StreamAxioms(constraints=()))._run(s) as it:
        rows = list(it)

    assert len(rows) == 1
    h, data = rows[0]
    assert isinstance(h, AxiomHash)
    assert h == HashedAxiom.of(decl).hash
    payload = json.loads(data)
    assert payload["iri"] == "ex:Dog"


def test_run_yields_in_hash_order(s):
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
    ]
    add_axioms(s, decls)

    with (StreamAxioms(constraints=()))._run(s) as it:
        hashes = [h for h, _ in it]

    assert hashes == sorted(hashes)


def test_run_filter_by_of_types(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
        ],
    )
    with (StreamAxioms(constraints=(WithTypes(tags=(AxiomTag.SUB_CLASS_OF,)),)))._run(s) as it:
        rows = list(it)

    assert len(rows) == 1


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    with (StreamAxioms(constraints=(AlwaysFalse(),)))._run(s) as it:
        assert list(it) == []


def test_run_early_break_closes_cleanly(s):
    decls = [Declaration(entity_type=EntityType.CLASS, iri=IRI(f"ex:C{i}")) for i in range(10)]
    add_axioms(s, decls)

    seen: list[AxiomHash] = []
    with (StreamAxioms(constraints=()))._run(s) as it:
        for h, _ in it:
            seen.append(h)
            if len(seen) == 3:
                break

    # Iteration stopped early but the context manager still runs cleanup.
    assert len(seen) == 3
    # The session must remain usable after early break.
    with (StreamAxioms(constraints=()))._run(s) as it2:
        assert sum(1 for _ in it2) == 10


def test_run_iteration_lazy_within_with_block(s):
    # The iterator yields rows one at a time inside the `with` block.
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
    ]
    add_axioms(s, decls)

    with (StreamAxioms(constraints=()))._run(s) as it:
        first = next(it)
        rest = list(it)

    assert isinstance(first[0], AxiomHash)
    assert len(rest) == 2
