"""List axioms (hash + JSON data) matching a constraint set, in stable hash order."""

from typing import override

from ontoloom.axioms.hashing import AxiomHash
from ontoloom.connection import Session
from ontoloom.query._predicates import build_axiom_predicate
from ontoloom.query.base import Query, RenderedSql
from ontoloom.query.constraints import HasAxiomConstraints


class ListAxioms(HasAxiomConstraints, Query[list[tuple[AxiomHash, str]]]):
    @override
    def render(self) -> RenderedSql:
        pred = build_axiom_predicate(self.constraints)
        sql = f"SELECT a.hash, json(a.data) FROM axioms a WHERE {pred.sql} ORDER BY a.hash"
        return RenderedSql(sql=sql, params=pred.params)

    @override
    def _run(self, s: Session) -> list[tuple[AxiomHash, str]]:
        compiled = self.render()
        return [(AxiomHash(r[0]), r[1]) for r in s.conn.execute(compiled.sql, compiled.params)]
