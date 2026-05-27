from ontoloom.axioms.types import AxiomSummary
from ontoloom.connection import Session
from ontoloom.query.constraints import AxiomConstraint
from ontoloom.query.count_axioms_by_type import CountAxiomsByType
from ontoloom.query.dispatch import resolve_within, run
from ontoloom.selections.types import SelectionName


def axiom_summary(
    s: Session,
    *,
    within: SelectionName | None = None,
) -> AxiomSummary:
    constraints: tuple[AxiomConstraint, ...] = (resolve_within(s, within),) if within else ()
    by_type = run(s, CountAxiomsByType(constraints=constraints))
    return AxiomSummary(total=sum(by_type.values()), by_type=by_type)
