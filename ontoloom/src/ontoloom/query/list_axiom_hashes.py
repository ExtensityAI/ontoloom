"""List axiom hashes matching a constraint set, with stable pagination."""

from pydantic import model_validator

from ontoloom.connection import Session
from ontoloom.hashing import AxiomHash
from ontoloom.models import FrozenModel
from ontoloom.query._constraints import AxiomConstraint
from ontoloom.query._normalize import normalize_axiom
from ontoloom.query._predicates import CompiledSql, _axiom_predicates


class ListAxiomHashes(FrozenModel):
    constraints: tuple[AxiomConstraint, ...]
    limit: int | None = None
    offset: int = 0

    @model_validator(mode="after")
    def _validate_pagination(self) -> "ListAxiomHashes":
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


def normalize(q: ListAxiomHashes) -> ListAxiomHashes:
    return q.model_copy(update={"constraints": normalize_axiom(q.constraints)})


def render(q: ListAxiomHashes) -> CompiledSql:
    predicate, params = _axiom_predicates(q.constraints)
    sql_parts = ["SELECT a.hash FROM axioms a"]

    if predicate != "1":
        sql_parts.append(f"WHERE {predicate}")

    sql_parts.append("ORDER BY a.hash")

    if q.limit is not None:
        sql_parts.append("LIMIT ?")
        params.append(q.limit)

        if q.offset > 0:
            sql_parts.append("OFFSET ?")
            params.append(q.offset)

    return CompiledSql(sql=" ".join(sql_parts), params=tuple(params))


def _run(s: Session, q: ListAxiomHashes) -> list[AxiomHash]:
    compiled = render(normalize(q))
    return [AxiomHash(r[0]) for r in s._conn.execute(compiled.sql, compiled.params)]
