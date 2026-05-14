"""Stream axioms (hash + JSON data) matching a constraint set; caller owns cursor lifetime."""

from collections.abc import Iterator
from contextlib import contextmanager

from ontoloom.connection import Session
from ontoloom.hashing import AxiomHash
from ontoloom.models import FrozenModel
from ontoloom.query._constraints import AxiomConstraint
from ontoloom.query._normalize import normalize_axiom
from ontoloom.query._predicates import CompiledSql, _axiom_predicates


class StreamAxioms(FrozenModel):
    constraints: tuple[AxiomConstraint, ...]


def normalize(q: StreamAxioms) -> StreamAxioms:
    return q.model_copy(update={"constraints": normalize_axiom(q.constraints)})


def render(q: StreamAxioms) -> CompiledSql:
    predicate, params = _axiom_predicates(q.constraints)
    sql_parts = ["SELECT a.hash, json(a.data) FROM axioms a"]

    if predicate != "1":
        sql_parts.append(f"WHERE {predicate}")

    sql_parts.append("ORDER BY a.hash")
    return CompiledSql(sql=" ".join(sql_parts), params=tuple(params))


@contextmanager
def _run(s: Session, q: StreamAxioms) -> Iterator[Iterator[tuple[AxiomHash, str]]]:
    compiled = render(normalize(q))
    cursor = s._conn.execute(compiled.sql, compiled.params)
    try:
        yield ((AxiomHash(h), data) for h, data in cursor)
    finally:
        cursor.close()
