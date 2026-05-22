"""Tests for the ListAxioms / ListAxiomHashes / StreamAxioms query trio.

The three queries share constraint handling and ordering; they differ in
projection (`a.hash` vs `a.hash, json(a.data)`), pagination support
(StreamAxioms has none), and return shape (list vs streaming context manager).
Common cases are parametrized over the trio; the per-query specifics
(JSON payload shape, streaming lifecycle, pagination semantics) and the
ListAxiomHashes-only annotation predicates live in dedicated sections.
"""

import json
from collections.abc import Callable
from typing import Any

import pytest
from ontoloom.axioms.mutations import add_axioms
from ontoloom.axioms.types import HashedAxiom
from ontoloom.connection import Session
from ontoloom.hashing import AxiomHash
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import AxiomTag, Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.query.constraints import (
    AlwaysFalse,
    HasAnyAnnotation,
    TextMatchKind,
    WithAnnotationText,
    WithTypes,
)
from ontoloom.query.dispatch import run
from ontoloom.query.list_axiom_hashes import ListAxiomHashes
from ontoloom.query.list_axioms import ListAxioms
from ontoloom.query.stream_axioms import StreamAxioms

# ---- adapter helpers ----------------------------------------------------------

# Each query has a different result shape. To share run-tests we normalize all
# three to `list[AxiomHash]` via a small adapter.

ResultHashes = Callable[[Any, Session], list[AxiomHash]]


def _list_hashes_hashes(q: ListAxiomHashes, s: Session) -> list[AxiomHash]:
    return run(s, q)


def _list_axioms_hashes(q: ListAxioms, s: Session) -> list[AxiomHash]:
    return [h for h, _ in run(s, q)]


def _stream_axioms_hashes(q: StreamAxioms, s: Session) -> list[AxiomHash]:
    with run(s, q) as it:
        return [h for h, _ in it]


# (id, query_class, projection_sql, supports_pagination, run_adapter)
TRIO: list[tuple[str, type, str, bool, ResultHashes]] = [
    ("hashes", ListAxiomHashes, "SELECT a.hash", True, _list_hashes_hashes),
    ("axioms", ListAxioms, "SELECT a.hash, json(a.data)", True, _list_axioms_hashes),
    ("stream", StreamAxioms, "SELECT a.hash, json(a.data)", False, _stream_axioms_hashes),
]


def _make(query_cls: type, *, constraints: tuple = (), limit: int | None = None, offset: int = 0):
    """Construct a query, omitting pagination args for queries that don't support them."""
    if query_cls is StreamAxioms:
        return query_cls(constraints=constraints)

    return query_cls(constraints=constraints, limit=limit, offset=offset)


# ---- shared run tests --------------------------------------------------------


@pytest.mark.parametrize(
    ("query_cls", "run_hashes"),
    [(cls, runner) for _, cls, _, _, runner in TRIO],
    ids=[ident for ident, *_ in TRIO],
)
def test_run_empty_ontology(s, query_cls: type, run_hashes: ResultHashes):
    assert run_hashes(_make(query_cls), s) == []


@pytest.mark.parametrize(
    ("query_cls", "run_hashes"),
    [(cls, runner) for _, cls, _, _, runner in TRIO],
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
    [(cls, runner) for _, cls, _, _, runner in TRIO],
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
    [(cls, runner) for _, cls, _, _, runner in TRIO],
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


@pytest.mark.parametrize(
    ("query_cls", "run_hashes"),
    [(cls, runner) for _, cls, _, _, runner in TRIO],
    ids=[ident for ident, *_ in TRIO],
)
def test_run_always_false(s, query_cls: type, run_hashes: ResultHashes):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert run_hashes(_make(query_cls, constraints=(AlwaysFalse(),)), s) == []


# ---- pagination run (paginated queries only) ---------------------------------


@pytest.mark.parametrize(
    ("query_cls", "run_hashes"),
    [(cls, runner) for _, cls, _, pag, runner in TRIO if pag],
    ids=[ident for ident, _, _, pag, _ in TRIO if pag],
)
def test_run_pagination_stable(s, query_cls: type, run_hashes: ResultHashes):
    decls = [Declaration(entity_type=EntityType.CLASS, iri=IRI(f"ex:C{i}")) for i in range(6)]
    add_axioms(s, decls)
    page1 = run_hashes(_make(query_cls, limit=2), s)
    page2 = run_hashes(_make(query_cls, limit=2, offset=2), s)
    assert len(page1) == 2
    assert len(page2) == 2
    assert set(page1).isdisjoint(page2)


@pytest.mark.parametrize(
    ("query_cls", "run_hashes"),
    [(cls, runner) for _, cls, _, pag, runner in TRIO if pag],
    ids=[ident for ident, _, _, pag, _ in TRIO if pag],
)
def test_run_pagination_full_walk(s, query_cls: type, run_hashes: ResultHashes):
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
    ]
    add_axioms(s, decls)
    full = run_hashes(_make(query_cls), s)
    paged = (
        run_hashes(_make(query_cls, limit=1), s)
        + run_hashes(_make(query_cls, limit=1, offset=1), s)
        + run_hashes(_make(query_cls, limit=1, offset=2), s)
    )
    assert paged == full


# ---- ListAxioms-specific: JSON payload shape ---------------------------------


def test_list_axioms_run_returns_hash_and_json(s):
    decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    add_axioms(s, [decl])
    result = run(s, ListAxioms(constraints=()))
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
    with run(s, StreamAxioms(constraints=())) as it:
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
    with run(s, StreamAxioms(constraints=())) as it:
        for h, _ in it:
            seen.append(h)
            if len(seen) == 3:
                break

    assert len(seen) == 3
    # The session must remain usable after early break.
    with run(s, StreamAxioms(constraints=())) as it2:
        assert sum(1 for _ in it2) == 10


def test_stream_run_iteration_lazy_within_with_block(s):
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
    ]
    add_axioms(s, decls)
    with run(s, StreamAxioms(constraints=())) as it:
        first = next(it)
        rest = list(it)
    assert isinstance(first[0], AxiomHash)
    assert len(rest) == 2


# ---- ListAxiomHashes-specific: WithAnnotationText predicate ------------------
#
# Annotation predicates are query-agnostic (they live in `_axiom_predicates`),
# but the existing coverage exercises them through ListAxiomHashes. Kept here
# unparametrized — the predicate is what's under test, not the projection.


def _comment(text: str) -> Annotation:
    return Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value=text))


def _label(text: str) -> Annotation:
    return Annotation(property=IRI("rdfs:label"), value=LangLiteral(value=text))


def test_run_with_annotation_text_substring_matches_partial(s):
    matching = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("this is a TODO note"),),
    )
    other = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("unrelated content"),),
    )
    add_axioms(s, [matching, other])
    result = run(s, ListAxiomHashes(constraints=(WithAnnotationText(text="TODO"),)))
    assert result == [HashedAxiom.of(matching).hash]


def test_run_with_annotation_text_exact_no_substring(s):
    exact = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("TODO"),),
    )
    superstring = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("TODO and more"),),
    )
    add_axioms(s, [exact, superstring])
    result = run(
        s,
        ListAxiomHashes(
            constraints=(WithAnnotationText(text="TODO", match_kind=TextMatchKind.EXACT),),
        ),
    )
    assert result == [HashedAxiom.of(exact).hash]


def test_run_with_annotation_text_restricts_to_properties(s):
    commented = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("X"),),
    )
    labelled = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(_label("X"),),
    )
    add_axioms(s, [commented, labelled])
    result = run(
        s,
        ListAxiomHashes(
            constraints=(WithAnnotationText(text="X", properties=(IRI("rdfs:comment"),)),),
        ),
    )
    assert result == [HashedAxiom.of(commented).hash]


def test_run_with_annotation_text_empty_result(s):
    add_axioms(
        s,
        [
            SubClassOf(
                sub_class=IRI("ex:Dog"),
                super_class=IRI("ex:Animal"),
                annotations=(_comment("hello"),),
            ),
        ],
    )
    result = run(s, ListAxiomHashes(constraints=(WithAnnotationText(text="nonexistent"),)))
    assert result == []


# ---- ListAxiomHashes-specific: HasAnyAnnotation predicate --------------------


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
    result = run(
        s,
        ListAxiomHashes(
            constraints=(HasAnyAnnotation(properties=(IRI("rdfs:isDefinedBy"),)),),
        ),
    )
    assert result == [HashedAxiom.of(sourced).hash]
