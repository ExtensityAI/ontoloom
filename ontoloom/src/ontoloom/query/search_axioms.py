"""Annotation-text axiom search with exact-then-substring ranking.

Exact matches on `axiom_text.text` outrank substring matches; within each rank
the order is by axiom hash. Optional `properties` restrict the search to a set
of annotation property IRIs. Additional axiom constraints (e.g. `InSelection`)
narrow the candidate set before ranking.

Pagination (`limit`/`offset`) is applied after ranking; `total` reports the
full match count independent of pagination.
"""

from dataclasses import dataclass
from typing import override

from ontoloom.connection import Session
from ontoloom.hashing import AxiomHash
from ontoloom.owl.iri import IRI
from ontoloom.query._predicates import _axiom_predicates
from ontoloom.query.base import Query, RenderedSql
from ontoloom.query.constraints import AxiomConstraint, HasAxiomConstraints, HasPagination

RANK_EXACT = 0
RANK_SUBSTRING = 1


@dataclass(frozen=True, slots=True)
class SearchAxiomsHit:
    hash: AxiomHash
    rank: int  # 0 = exact, 1 = substring


@dataclass(frozen=True, slots=True)
class SearchAxiomsResult:
    hits: tuple[SearchAxiomsHit, ...]
    total: int


class SearchAxioms(HasAxiomConstraints, HasPagination, Query[SearchAxiomsResult]):
    query: str
    properties: tuple[IRI, ...] = ()
    constraints: tuple[AxiomConstraint, ...] = ()

    @override
    def render(self) -> RenderedSql:
        # SearchAxioms composes two SQL statements; render() returns the exact
        # arm so RenderedSql remains a single, debuggable string. Real execution
        # goes through `_run`.
        return _render_arm(self, exact=True)

    @override
    def _run(self, s: Session) -> SearchAxiomsResult:
        exact_sql = _render_arm(self, exact=True)
        substring_sql = _render_arm(self, exact=False)

        exact_hashes = [AxiomHash(r[0]) for r in s.conn.execute(exact_sql.sql, exact_sql.params)]
        exact_set = set(exact_hashes)
        substring_hashes = [
            AxiomHash(r[0])
            for r in s.conn.execute(substring_sql.sql, substring_sql.params)
            if AxiomHash(r[0]) not in exact_set
        ]

        ranked: list[SearchAxiomsHit] = [
            SearchAxiomsHit(hash=h, rank=RANK_EXACT) for h in exact_hashes
        ]
        ranked.extend(SearchAxiomsHit(hash=h, rank=RANK_SUBSTRING) for h in substring_hashes)

        total = len(ranked)
        offset = self.offset
        end = offset + self.limit if self.limit is not None else len(ranked)
        page = tuple(ranked[offset:end])

        return SearchAxiomsResult(hits=page, total=total)


def _render_arm(q: SearchAxioms, *, exact: bool) -> RenderedSql:
    pred = _axiom_predicates(q.constraints)

    text_op = "LOWER(at.text) = ?" if exact else "INSTR(LOWER(at.text), ?) > 0"
    params: list[object] = []

    if q.properties:
        placeholders = ",".join("?" for _ in q.properties)
        text_exists = (
            f"EXISTS (SELECT 1 FROM axiom_text at "
            f"WHERE at.axiom_id = a.id "
            f"AND at.property IN ({placeholders}) AND {text_op})"
        )
        params.extend(q.properties)
    else:
        text_exists = f"EXISTS (SELECT 1 FROM axiom_text at WHERE at.axiom_id = a.id AND {text_op})"

    params.append(q.query.lower())

    sql = f"SELECT a.hash FROM axioms a WHERE {pred.sql} AND {text_exists} ORDER BY a.hash"

    return RenderedSql(sql=sql, params=(*pred.params, *params))
