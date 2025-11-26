from abc import ABC, abstractmethod
from typing import Self

from ontology_hydra.ontology.state.models import Model, OntologyState, vartuple
from ontology_hydra.ontology.state.update.effects import Effect
from ontology_hydra.ontology.state.update.preconditions import Precondition


class BaseOperationArgs(Model):
    pass


class BaseOperation[A: BaseOperationArgs](ABC):
    def __init__(self, args: A, preconditions: vartuple[Precondition], effects: vartuple[Effect]):
        self._args = args
        self._preconditions = preconditions
        self._effects = effects

    @property
    def args(self) -> A:
        return self._args

    @property
    def preconditions(self) -> vartuple[Precondition]:
        return self._preconditions

    @property
    def effects(self) -> vartuple[Effect]:
        return self._effects

    def test_for_unsatisfied_preconditions(self, state: OntologyState) -> vartuple[Precondition]:
        """Check for unmet preconditions without applying the operation."""
        return tuple(req for req in self._preconditions if not req.is_satisfied_in(state))

    def try_apply(self, state: OntologyState) -> Result:
        unsatisfied_preconditions = self.test_for_unsatisfied_preconditions(state)

        if len(unsatisfied_preconditions) > 0:
            # some preconditions are not satisfied, return early and do not apply
            return UnsatisfiedRequirementsFailure(
                unsatisfied_requirements=unsatisfied_preconditions,
            )

        try:
            return Success(state=self._apply(state))
        except Exception:
            return ExceptionFailure()

    @abstractmethod
    def _apply(self, state: OntologyState) -> OntologyState:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_args(cls, args: A) -> Self:
        raise NotImplementedError
