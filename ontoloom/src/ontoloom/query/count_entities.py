"""Count distinct entities matching a constraint set."""

from ontoloom.connection import Session
from ontoloom.models import FrozenModel
from ontoloom.query._constraints import EntityConstraint
from ontoloom.query._normalize import normalize_entity
from ontoloom.query._predicates import CompiledSql, _entity_predicates


class CountEntities(FrozenModel):
    constraints: tuple[EntityConstraint, ...]


def normalize(q: CountEntities) -> CountEntities:
    return q.model_copy(update={"constraints": normalize_entity(q.constraints)})


def render(q: CountEntities) -> CompiledSql:
    predicate, params = _entity_predicates(q.constraints)

    if predicate == "1":
        sql = "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae"
    else:
        sql = f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE {predicate}"

    return CompiledSql(sql=sql, params=tuple(params))


def _run(s: Session, q: CountEntities) -> int:
    compiled = render(normalize(q))
    return s._conn.execute(compiled.sql, compiled.params).fetchone()[0]
