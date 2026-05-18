"""Count axioms grouped by their type tag."""

from collections import Counter
from typing import override

from ontoloom.connection import Session
from ontoloom.owl.markers import AxiomTag
from ontoloom.query._predicates import _axiom_predicates
from ontoloom.query.base import Query
from ontoloom.query.constraints import HasAxiomConstraints
from ontoloom.query.rendered import RenderedSql


class CountAxiomsByType(HasAxiomConstraints, Query[Counter[AxiomTag]]):
    @override
    def render(self) -> RenderedSql:
        pred = _axiom_predicates(self.constraints)
        sql = f"SELECT a.type, COUNT(*) FROM axioms a WHERE {pred.sql} GROUP BY a.type"
        return RenderedSql(sql=sql, params=pred.params)

    @override
    def _run(self, s: Session) -> Counter[AxiomTag]:
        compiled = self.render()
        rows = s.conn.execute(compiled.sql, compiled.params).fetchall()
        return Counter({AxiomTag(r[0]): r[1] for r in rows})
