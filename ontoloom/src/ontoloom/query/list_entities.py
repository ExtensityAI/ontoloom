"""List distinct entity IRIs matching a constraint set, with stable pagination."""

from typing import override

from ontoloom.connection import Session
from ontoloom.owl.iri import IRI
from ontoloom.query._predicates import _entity_predicates
from ontoloom.query.base import Query
from ontoloom.query.constraints import HasEntityConstraints, HasPagination
from ontoloom.query.rendered import RenderedSql


class ListEntities(HasEntityConstraints, HasPagination, Query[list[IRI]]):
    @override
    def render(self) -> RenderedSql:
        pred = _entity_predicates(self.constraints)
        sql_parts = [
            f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae WHERE {pred.sql}",
            "ORDER BY ae.entity_iri",
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
    def _run(self, s: Session) -> list[IRI]:
        compiled = self.render()
        return [IRI(r[0]) for r in s.conn.execute(compiled.sql, compiled.params)]
