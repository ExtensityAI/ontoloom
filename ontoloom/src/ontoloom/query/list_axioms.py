"""List axioms (hash + JSON data) matching a constraint set, with stable pagination."""

from typing import override

from ontoloom.connection import Session
from ontoloom.hashing import AxiomHash
from ontoloom.query._predicates import _axiom_predicates
from ontoloom.query.base import Query
from ontoloom.query.constraints import HasAxiomConstraints, HasPagination
from ontoloom.query.rendered import RenderedSql


class ListAxioms(HasAxiomConstraints, HasPagination, Query[list[tuple[AxiomHash, str]]]):
    @override
    def render(self) -> RenderedSql:
        pred = _axiom_predicates(self.constraints)
        sql_parts = [
            f"SELECT a.hash, json(a.data) FROM axioms a WHERE {pred.sql}",
            "ORDER BY a.hash",
        ]
        params: list[object] = list(pred.params)

        if self.limit is not None:
            sql_parts.append("LIMIT ?")
            params.append(self.limit)

            if self.offset > 0:
                sql_parts.append("OFFSET ?")
                params.append(self.offset)

        return RenderedSql(sql=" ".join(sql_parts), params=tuple(params))

    @override
    def _run(self, s: Session) -> list[tuple[AxiomHash, str]]:
        compiled = self.render()
        return [(AxiomHash(r[0]), r[1]) for r in s.conn.execute(compiled.sql, compiled.params)]
