"""List axiom hashes matching a constraint set, with stable pagination."""

from typing import override

from ontoloom.axioms.hashing import AxiomHash
from ontoloom.connection import Session
from ontoloom.query._predicates import _axiom_predicates
from ontoloom.query.base import Query, RenderedSql, append_pagination
from ontoloom.query.constraints import HasAxiomConstraints, HasPagination


class ListAxiomHashes(HasAxiomConstraints, HasPagination, Query[list[AxiomHash]]):
    @override
    def render(self) -> RenderedSql:
        pred = _axiom_predicates(self.constraints)
        sql_parts = [
            f"SELECT a.hash FROM axioms a WHERE {pred.sql}",
            "ORDER BY a.hash",
        ]
        params: list[object] = list(pred.params)
        append_pagination(sql_parts, params, self.limit, self.offset)
        return RenderedSql(sql=" ".join(sql_parts), params=tuple(params))

    @override
    def _run(self, s: Session) -> list[AxiomHash]:
        compiled = self.render()
        return [AxiomHash(r[0]) for r in s.conn.execute(compiled.sql, compiled.params)]
