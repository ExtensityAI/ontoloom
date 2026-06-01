from ontoloom.axioms.types import AxiomSummary
from ontoloom.connection import Session
from ontoloom.query.constraints import AxiomConstraint
from ontoloom.query.count_axioms_by_type import CountAxiomsByType
from ontoloom.query.dispatch import execute, resolve_within
from ontoloom.selections.types import SelectionName


def summarize_axioms(
    s: Session,
    *,
    within: SelectionName | None = None,
) -> AxiomSummary:
    constraints: tuple[AxiomConstraint, ...] = (resolve_within(s, within),) if within else ()
    by_type = execute(s, CountAxiomsByType(constraints=constraints))
    return AxiomSummary(total=sum(by_type.values()), by_type=by_type)
