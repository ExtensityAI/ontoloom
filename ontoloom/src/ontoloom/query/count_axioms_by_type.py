"""Count axioms grouped by their type tag."""

from collections import Counter

from ontoloom.connection import Session
from ontoloom.models import FrozenModel
from ontoloom.query._constraints import AxiomConstraint
from ontoloom.query._normalize import normalize_axiom
from ontoloom.query._predicates import CompiledSql, _axiom_predicates


class CountAxiomsByType(FrozenModel):
    constraints: tuple[AxiomConstraint, ...]


def normalize(q: CountAxiomsByType) -> CountAxiomsByType:
    return q.model_copy(update={"constraints": normalize_axiom(q.constraints)})


def render(q: CountAxiomsByType) -> CompiledSql:
    predicate, params = _axiom_predicates(q.constraints)

    if predicate == "1":
        sql = "SELECT a.type, COUNT(*) FROM axioms a GROUP BY a.type"
    else:
        sql = f"SELECT a.type, COUNT(*) FROM axioms a WHERE {predicate} GROUP BY a.type"

    return CompiledSql(sql=sql, params=tuple(params))


def _run(s: Session, q: CountAxiomsByType) -> Counter[str]:
    compiled = render(normalize(q))
    rows = s._conn.execute(compiled.sql, compiled.params).fetchall()
    return Counter({r[0]: r[1] for r in rows})
