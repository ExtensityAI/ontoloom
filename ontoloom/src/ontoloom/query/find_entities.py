"""Find distinct entity IRIs matching a constraint set, ranked then IRI-ordered."""

from typing import override

from ontoloom.connection import Session
from ontoloom.owl.iri import IRI
from ontoloom.query._predicates import _entity_predicates
from ontoloom.query.base import Query, RenderedSql
from ontoloom.query.constraints import HasEntityConstraints


class FindEntities(HasEntityConstraints, Query[list[IRI]]):
    @override
    def render(self) -> RenderedSql:
        pred = _entity_predicates(self.constraints)
        order_terms = [rt.sql for rt in pred.rank] + ["ae.entity_iri"]
        sql = (
            f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae WHERE {pred.sql} "
            f"ORDER BY {', '.join(order_terms)}"
        )
        params: tuple[object, ...] = (*pred.params, *(p for rt in pred.rank for p in rt.params))
        return RenderedSql(sql=sql, params=params)

    @override
    def _run(self, s: Session) -> list[IRI]:
        compiled = self.render()
        return [IRI(r[0]) for r in s.conn.execute(compiled.sql, compiled.params)]
