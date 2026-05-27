"""Annotation-text axiom search with exact-then-substring ranking.

Exact matches on `axiom_text.text` outrank substring matches; within each rank
the order is by axiom hash. Optional `properties` restrict the search to a set
of annotation property IRIs. Additional axiom constraints (e.g. `InAxiomSelection`)
narrow the candidate set before ranking.
"""

from typing import override

from ontoloom.axioms.hashing import AxiomHash
from ontoloom.connection import Session
from ontoloom.owl.iri import IRI
from ontoloom.query._predicates import _axiom_predicates
from ontoloom.query.base import Query, RenderedSql
from ontoloom.query.constraints import AxiomConstraint, HasAxiomConstraints

RANK_EXACT = 0
RANK_SUBSTRING = 1


class SearchAxioms(HasAxiomConstraints, Query[list[AxiomHash]]):
    query: str
    properties: tuple[IRI, ...] = ()
    constraints: tuple[AxiomConstraint, ...] = ()

    @override
    def render(self) -> RenderedSql:
        cte_sql, cte_params = _render_ctes(self)
        sql = " ".join(
            [
                cte_sql,
                f"SELECT hash, {RANK_EXACT} AS rank FROM exact",
                "UNION ALL",
                f"SELECT hash, {RANK_SUBSTRING} AS rank FROM substring_only",
                "ORDER BY rank, hash",
            ]
        )
        return RenderedSql(sql=sql, params=tuple(cte_params))

    @override
    def _run(self, s: Session) -> list[AxiomHash]:
        page = self.render()
        rows = s.conn.execute(page.sql, page.params).fetchall()
        return [AxiomHash(h) for h, _rank in rows]


def _render_ctes(q: SearchAxioms) -> tuple[str, tuple[object, ...]]:
    """Render the WITH clause containing `exact` and `substring_only` CTEs.

    `substring_only` excludes hashes already in `exact` so the UNION ALL has no
    duplicates and rank-0 hits always sort before rank-1.
    """
    exact_arm, exact_params = _arm_sql(q, exact=True)
    substring_arm, substring_params = _arm_sql(q, exact=False)

    sql = (
        f"WITH exact AS ({exact_arm}), "
        f"substring_only AS ({substring_arm} AND a.hash NOT IN (SELECT hash FROM exact))"
    )
    return sql, (*exact_params, *substring_params)


def _arm_sql(q: SearchAxioms, *, exact: bool) -> tuple[str, tuple[object, ...]]:
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

    sql = f"SELECT a.hash AS hash FROM axioms a WHERE {pred.sql} AND {text_exists}"
    return sql, (*pred.params, *params)
