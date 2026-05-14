"""Count distinct entities grouped by their OWL role."""

from collections import Counter

from ontoloom.connection import Session
from ontoloom.models import FrozenModel
from ontoloom.owl.markers import EntityType
from ontoloom.query._constraints import EntityConstraint
from ontoloom.query._normalize import normalize_entity
from ontoloom.query._predicates import CompiledSql, _entity_predicates


class CountEntitiesByRole(FrozenModel):
    constraints: tuple[EntityConstraint, ...]


def normalize(q: CountEntitiesByRole) -> CountEntitiesByRole:
    return q.model_copy(update={"constraints": normalize_entity(q.constraints)})


def render(q: CountEntitiesByRole) -> CompiledSql:
    predicate, params = _entity_predicates(q.constraints)
    sql = (
        "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        f"WHERE {predicate} AND ae.role IS NOT NULL "
        "GROUP BY ae.role"
    )
    return CompiledSql(sql=sql, params=tuple(params))


def _run(s: Session, q: CountEntitiesByRole) -> Counter[EntityType]:
    compiled = render(normalize(q))
    rows = s._conn.execute(compiled.sql, compiled.params).fetchall()
    return Counter({EntityType(r[0]): r[1] for r in rows})
