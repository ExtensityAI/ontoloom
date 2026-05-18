"""Count distinct entities grouped by their OWL role."""

from collections import Counter
from typing import override

from ontoloom.connection import Session
from ontoloom.owl.markers import EntityType
from ontoloom.query._predicates import _entity_predicates
from ontoloom.query.base import Query
from ontoloom.query.constraints import HasEntityConstraints
from ontoloom.query.rendered import RenderedSql


class CountEntitiesByRole(HasEntityConstraints, Query[Counter[EntityType]]):
    @override
    def render(self) -> RenderedSql:
        pred = _entity_predicates(self.constraints)
        sql = (
            "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
            f"WHERE {pred.sql} AND ae.role IS NOT NULL "
            "GROUP BY ae.role"
        )
        return RenderedSql(sql=sql, params=pred.params)

    @override
    def _run(self, s: Session) -> Counter[EntityType]:
        compiled = self.render()
        rows = s.conn.execute(compiled.sql, compiled.params).fetchall()
        return Counter({EntityType(r[0]): r[1] for r in rows})
