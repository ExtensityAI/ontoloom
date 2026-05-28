"""Find axiom hashes matching a constraint set, ranked then hash-ordered."""

from typing import override

from ontoloom.axioms.hashing import AxiomHash
from ontoloom.connection import Session
from ontoloom.query._predicates import build_axiom_predicate
from ontoloom.query.base import Query, RenderedSql
from ontoloom.query.constraints import HasAxiomConstraints


class FindAxioms(HasAxiomConstraints, Query[list[AxiomHash]]):
    @override
    def render(self) -> RenderedSql:
        pred = build_axiom_predicate(self.constraints)
        order_terms = [rt.sql for rt in pred.rank] + ["a.hash"]
        sql = f"SELECT a.hash FROM axioms a WHERE {pred.sql} ORDER BY {', '.join(order_terms)}"
        params: tuple[object, ...] = (
            *pred.params,
            *(p for rt in pred.rank for p in rt.params),
        )
        return RenderedSql(sql=sql, params=params)

    @override
    def _run(self, s: Session) -> list[AxiomHash]:
        compiled = self.render()
        return [AxiomHash(r[0]) for r in s.conn.execute(compiled.sql, compiled.params)]
