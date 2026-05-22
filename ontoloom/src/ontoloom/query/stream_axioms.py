"""Stream axioms (hash + JSON data) matching a constraint set; caller owns cursor lifetime."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import override

from ontoloom.axioms.hashing import AxiomHash
from ontoloom.connection import Session
from ontoloom.query._predicates import _axiom_predicates
from ontoloom.query.base import Query, RenderedSql
from ontoloom.query.constraints import HasAxiomConstraints


class StreamAxioms(
    HasAxiomConstraints,
    Query[AbstractContextManager[Iterator[tuple[AxiomHash, str]]]],
):
    @override
    def render(self) -> RenderedSql:
        pred = _axiom_predicates(self.constraints)
        sql = f"SELECT a.hash, json(a.data) FROM axioms a WHERE {pred.sql} ORDER BY a.hash"
        return RenderedSql(sql=sql, params=pred.params)

    @override
    @contextmanager
    def _run(self, s: Session) -> Iterator[Iterator[tuple[AxiomHash, str]]]:
        compiled = self.render()
        cursor = s.conn.execute(compiled.sql, compiled.params)
        try:
            yield ((AxiomHash(h), data) for h, data in cursor)
        finally:
            cursor.close()
