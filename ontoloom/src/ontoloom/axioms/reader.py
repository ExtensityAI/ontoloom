from ontoloom.axioms.types import AxiomSummary
from ontoloom.connection import Session
from ontoloom.query.constraints import (
    AxiomConstraint,
    InAxiomSelection,
    InEntitySelection,
)
from ontoloom.query.count_axioms_by_type import CountAxiomsByType
from ontoloom.query.dispatch import run
from ontoloom.selections.types import AxiomSelectionName, EntitySelectionName


def axiom_summary(
    s: Session,
    *,
    within: AxiomSelectionName | EntitySelectionName | None = None,
) -> AxiomSummary:
    constraints: tuple[AxiomConstraint, ...] = (_in_selection(within),) if within else ()
    by_type = run(s, CountAxiomsByType(constraints=constraints))
    return AxiomSummary(total=sum(by_type.values()), by_type=by_type)


def _in_selection(
    within: AxiomSelectionName | EntitySelectionName,
) -> AxiomConstraint:
    if isinstance(within, AxiomSelectionName):
        return InAxiomSelection(name=within)
    return InEntitySelection(name=within)
