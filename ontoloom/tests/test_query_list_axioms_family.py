"""Tests for the ListAxioms / FindAxioms / StreamAxioms query trio.

The three queries share constraint handling and ordering; they differ in
projection (`a.hash` vs `a.hash, json(a.data)`) and return shape (list vs
streaming context manager). None paginate — feed queries return the full
ordered result. Common cases are parametrized over the trio; the per-query
specifics (JSON payload shape, streaming lifecycle) and the FindAxioms-only
annotation predicates live in dedicated sections.
"""

import json
from collections.abc import Callable
from typing import Any

import pytest
from ontoloom.axioms.hashing import AxiomHash
from ontoloom.axioms.mutations import add_axioms
from ontoloom.axioms.types import HashedAxiom
from ontoloom.connection import Session
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import AxiomTag, Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.query.constraints import (
    HasAnyAnnotation,
    WithTypes,
)
from ontoloom.query.dispatch import execute
from ontoloom.query.find_axioms import FindAxioms
from ontoloom.query.list_axioms import ListAxioms
from ontoloom.query.stream_axioms import StreamAxioms

# ---- adapter helpers ----------------------------------------------------------

# Each query has a different result shape. To share run-tests we normalize all
# three to `list[AxiomHash]` via a small adapter.

ResultHashes = Callable[[Any, Session], list[AxiomHash]]


def _find_axioms_hashes(q: FindAxioms, s: Session) -> list[AxiomHash]:
    return execute(s, q)


def _list_axioms_hashes(q: ListAxioms, s: Session) -> list[AxiomHash]:
    return [h for h, _ in execute(s, q)]


def _stream_axioms_hashes(q: StreamAxioms, s: Session) -> list[AxiomHash]:
    with execute(s, q) as it:
        return [h for h, _ in it]


# (id, query_class, projection_sql, run_adapter)
TRIO: list[tuple[str, type, str, ResultHashes]] = [
    ("hashes", FindAxioms, "SELECT a.hash", _find_axioms_hashes),
    ("axioms", ListAxioms, "SELECT a.hash, json(a.data)", _list_axioms_hashes),
    ("stream", StreamAxioms, "SELECT a.hash, json(a.data)", _stream_axioms_hashes),
]


def _make(query_cls: type, *, constraints: tuple = ()):
    return query_cls(constraints=constraints)


# ---- shared run tests --------------------------------------------------------


@pytest.mark.parametrize(
    ("query_cls", "run_hashes"),
    [(cls, runner) for _, cls, _, runner in TRIO],
    ids=[ident for ident, *_ in TRIO],
)
def test_run_empty_ontology(s, query_cls: type, run_hashes: ResultHashes):
    assert run_hashes(_make(query_cls), s) == []


@pytest.mark.parametrize(
    ("query_cls", "run_hashes"),
    [(cls, runner) for _, cls, _, runner in TRIO],
    ids=[ident for ident, *_ in TRIO],
)
def test_run_yields_axiom_hash_typed_values(s, query_cls: type, run_hashes: ResultHashes):
    decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    add_axioms(s, [decl])
    result = run_hashes(_make(query_cls), s)
    assert len(result) == 1
    assert isinstance(result[0], AxiomHash)
    assert result[0] == HashedAxiom.of(decl).hash


@pytest.mark.parametrize(
    ("query_cls", "run_hashes"),
    [(cls, runner) for _, cls, _, runner in TRIO],
    ids=[ident for ident, *_ in TRIO],
)
def test_run_lists_in_hash_order(s, query_cls: type, run_hashes: ResultHashes):
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
    ]
    add_axioms(s, decls)
    hashes = run_hashes(_make(query_cls), s)
    assert hashes == sorted(hashes)


@pytest.mark.parametrize(
    ("query_cls", "run_hashes"),
    [(cls, runner) for _, cls, _, runner in TRIO],
    ids=[ident for ident, *_ in TRIO],
)
def test_run_filter_by_of_types(s, query_cls: type, run_hashes: ResultHashes):
    sub = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")), sub])
    result = run_hashes(
        _make(query_cls, constraints=(WithTypes(tags=(AxiomTag.SUB_CLASS_OF,)),)),
        s,
    )
    assert result == [HashedAxiom.of(sub).hash]


# ---- ListAxioms-specific: JSON payload shape ---------------------------------


def test_list_axioms_run_returns_hash_and_json(s):
    decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    add_axioms(s, [decl])
    result = execute(s, ListAxioms(constraints=()))
    assert len(result) == 1
    h, data = result[0]
    assert isinstance(h, AxiomHash)
    assert h == HashedAxiom.of(decl).hash
    assert isinstance(data, str)
    payload = json.loads(data)
    assert payload["entity_type"] == EntityType.CLASS
    assert payload["iri"] == "ex:Dog"


# ---- StreamAxioms-specific: streaming lifecycle ------------------------------


def test_stream_run_yields_hash_and_json(s):
    decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    add_axioms(s, [decl])
    with execute(s, StreamAxioms(constraints=())) as it:
        rows = list(it)
    assert len(rows) == 1
    h, data = rows[0]
    assert isinstance(h, AxiomHash)
    assert h == HashedAxiom.of(decl).hash
    payload = json.loads(data)
    assert payload["iri"] == "ex:Dog"


def test_stream_run_early_break_closes_cleanly(s):
    decls = [Declaration(entity_type=EntityType.CLASS, iri=IRI(f"ex:C{i}")) for i in range(10)]
    add_axioms(s, decls)

    seen: list[AxiomHash] = []
    with execute(s, StreamAxioms(constraints=())) as it:
        for h, _ in it:
            seen.append(h)
            if len(seen) == 3:
                break

    assert len(seen) == 3
    # The session must remain usable after early break.
    with execute(s, StreamAxioms(constraints=())) as it2:
        assert sum(1 for _ in it2) == 10


def test_stream_run_iteration_lazy_within_with_block(s):
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
    ]
    add_axioms(s, decls)
    with execute(s, StreamAxioms(constraints=())) as it:
        first = next(it)
        rest = list(it)
    assert isinstance(first[0], AxiomHash)
    assert len(rest) == 2


# ---- FindAxioms-specific: HasAnyAnnotation predicate -------------------------


def _comment(text: str) -> Annotation:
    return Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value=text))


def test_run_has_any_annotation_existence(s):
    sourced = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(
            Annotation(property=IRI("rdfs:isDefinedBy"), value=LangLiteral(value="imported")),
        ),
    )
    commented = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("doc"),),
    )
    unannotated = SubClassOf(
        sub_class=IRI("ex:Fox"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(s, [sourced, commented, unannotated])
    result = execute(
        s,
        FindAxioms(
            constraints=(HasAnyAnnotation(properties=(IRI("rdfs:isDefinedBy"),)),),
        ),
    )
    assert result == [HashedAxiom.of(sourced).hash]
