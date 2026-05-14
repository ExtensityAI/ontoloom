"""Tests for the StreamAxioms query."""

import json

from ontoloom.axioms.store import add_axioms
from ontoloom.hashing import AxiomHash, HashedAxiom
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query._constraints import AlwaysFalse, MentionsAny, OfTypes
from ontoloom.query.stream_axioms import StreamAxioms, _run, render

# -- render snapshots --


def test_render_no_constraints():
    compiled = render(StreamAxioms(constraints=()))
    assert compiled.sql == "SELECT a.hash, json(a.data) FROM axioms a ORDER BY a.hash"
    assert compiled.params == ()


def test_render_with_of_types():
    compiled = render(StreamAxioms(constraints=(OfTypes(tags=("Declaration",)),)))
    assert compiled.sql == (
        "SELECT a.hash, json(a.data) FROM axioms a WHERE a.type IN (?) ORDER BY a.hash"
    )
    assert compiled.params == ("Declaration",)


def test_render_with_mentions_any():
    compiled = render(StreamAxioms(constraints=(MentionsAny(iris=(IRI("ex:A"),)),)))
    assert compiled.sql == (
        "SELECT a.hash, json(a.data) FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri IN (?)) "
        "ORDER BY a.hash"
    )
    assert compiled.params == ("ex:A",)


def test_render_always_false():
    compiled = render(StreamAxioms(constraints=(AlwaysFalse(),)))
    assert compiled.sql == "SELECT a.hash, json(a.data) FROM axioms a WHERE 0 ORDER BY a.hash"
    assert compiled.params == ()


def test_render_always_includes_order_by():
    for q in [
        StreamAxioms(constraints=()),
        StreamAxioms(constraints=(OfTypes(tags=("Declaration",)),)),
        StreamAxioms(constraints=(AlwaysFalse(),)),
    ]:
        assert "ORDER BY a.hash" in render(q).sql


def test_render_no_pagination_clause():
    # Stream queries never emit LIMIT/OFFSET — the caller controls iteration.
    for q in [
        StreamAxioms(constraints=()),
        StreamAxioms(constraints=(OfTypes(tags=("Declaration",)),)),
    ]:
        sql = render(q).sql
        assert "LIMIT" not in sql
        assert "OFFSET" not in sql


# -- _run integration --


def test_run_empty_ontology(s):
    with _run(s, StreamAxioms(constraints=())) as it:
        assert list(it) == []


def test_run_yields_hash_and_json(s):
    decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    add_axioms(s, [decl])

    with _run(s, StreamAxioms(constraints=())) as it:
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

    with _run(s, StreamAxioms(constraints=())) as it:
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
    with _run(s, StreamAxioms(constraints=(OfTypes(tags=("SubClassOf",)),))) as it:
        rows = list(it)

    assert len(rows) == 1


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    with _run(s, StreamAxioms(constraints=(AlwaysFalse(),))) as it:
        assert list(it) == []


def test_run_early_break_closes_cleanly(s):
    decls = [Declaration(entity_type=EntityType.CLASS, iri=IRI(f"ex:C{i}")) for i in range(10)]
    add_axioms(s, decls)

    seen: list[AxiomHash] = []
    with _run(s, StreamAxioms(constraints=())) as it:
        for h, _ in it:
            seen.append(h)
            if len(seen) == 3:
                break

    # Iteration stopped early but the context manager still runs cleanup.
    assert len(seen) == 3
    # The session must remain usable after early break.
    with _run(s, StreamAxioms(constraints=())) as it2:
        assert sum(1 for _ in it2) == 10


def test_run_iteration_lazy_within_with_block(s):
    # The iterator yields rows one at a time inside the `with` block.
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
    ]
    add_axioms(s, decls)

    with _run(s, StreamAxioms(constraints=())) as it:
        first = next(it)
        rest = list(it)

    assert isinstance(first[0], AxiomHash)
    assert len(rest) == 2
