"""Count distinct entities matching a constraint set."""

from typing import override

from ontoloom.connection import Session
from ontoloom.query._predicates import build_entity_predicate
from ontoloom.query.base import Query, RenderedSql
from ontoloom.query.constraints import HasEntityConstraints


class CountEntities(HasEntityConstraints, Query[int]):
    @override
    def render(self) -> RenderedSql:
        pred = build_entity_predicate(self.constraints)
        sql = f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE {pred.sql}"
        return RenderedSql(sql=sql, params=pred.params)

    @override
    def _run(self, s: Session) -> int:
        compiled = self.render()
        return s.conn.execute(compiled.sql, compiled.params).fetchone()[0]
