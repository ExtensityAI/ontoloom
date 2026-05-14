"""List distinct entity IRIs matching a constraint set, with stable pagination."""

from pydantic import model_validator

from ontoloom.connection import Session
from ontoloom.models import FrozenModel
from ontoloom.owl.iri import IRI
from ontoloom.query._constraints import EntityConstraint
from ontoloom.query._normalize import normalize_entity
from ontoloom.query._predicates import CompiledSql, _entity_predicates


class ListEntities(FrozenModel):
    constraints: tuple[EntityConstraint, ...]
    limit: int | None = None
    offset: int = 0

    @model_validator(mode="after")
    def _validate_pagination(self) -> "ListEntities":
        if self.offset < 0:
            msg = "offset must be >= 0"
            raise ValueError(msg)

        if self.limit is not None and self.limit < 0:
            msg = "limit must be >= 0 if set"
            raise ValueError(msg)

        if self.offset > 0 and self.limit is None:
            msg = "offset > 0 requires limit to be set"
            raise ValueError(msg)

        return self


def normalize(q: ListEntities) -> ListEntities:
    return q.model_copy(update={"constraints": normalize_entity(q.constraints)})


def render(q: ListEntities) -> CompiledSql:
    predicate, params = _entity_predicates(q.constraints)
    sql_parts = ["SELECT DISTINCT ae.entity_iri FROM axiom_entities ae"]

    if predicate != "1":
        sql_parts.append(f"WHERE {predicate}")

    sql_parts.append("ORDER BY ae.entity_iri")

    if q.limit is not None:
        sql_parts.append("LIMIT ?")
        params.append(q.limit)

        if q.offset > 0:
            sql_parts.append("OFFSET ?")
            params.append(q.offset)

    return CompiledSql(sql=" ".join(sql_parts), params=tuple(params))


def _run(s: Session, q: ListEntities) -> list[IRI]:
    compiled = render(normalize(q))
    return [IRI(r[0]) for r in s._conn.execute(compiled.sql, compiled.params)]
