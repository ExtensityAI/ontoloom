from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Self

from ontology_hydra.ontology.state.models import Model, OntologyState, vartuple
from ontology_hydra.ontology.state.update.preconditions import Precondition


@dataclass(frozen=True, slots=True)
class Success:
    state: OntologyState
    success: Literal[True] = True
    type: Literal["success"] = "success"


@dataclass(frozen=True, slots=True)
class UnsatisfiedPreconditionsFailure:
    error: vartuple[Precondition]
    success: Literal[False] = False
    type: Literal["unsat_preconds"] = "unsat_preconds"


@dataclass(frozen=True, slots=True)
class ExceptionFailure:
    exception: Exception
    success: Literal[False] = False
    type: Literal["exception"] = "exception"


type Result = Success | UnsatisfiedPreconditionsFailure | ExceptionFailure


class BaseOperationArgs(Model):
    pass


class BaseOperation[A: BaseOperationArgs](ABC):
    def __init__(self, args: A, preconditions: vartuple[Precondition]):
        self._args = args
        self._preconditions = preconditions

    @property
    def args(self) -> A:
        return self._args

    @property
    def preconditions(self) -> vartuple[Precondition]:
        return self._preconditions

    def test_for_unsatisfied_preconditions(self, state: OntologyState) -> vartuple[Precondition]:
        """Check for unmet preconditions without applying the operation."""
        return tuple(req for req in self._preconditions if not req.is_satisfied_in(state))

    def try_apply(self, state: OntologyState) -> Result:
        unsat_preconds = self.test_for_unsatisfied_preconditions(state)

        if len(unsat_preconds) > 0:
            # some preconditions are not satisfied, return early and do not apply
            return UnsatisfiedPreconditionsFailure(error=unsat_preconds)

        try:
            return Success(state=self._apply(state))
        except Exception as e:
            return ExceptionFailure(exception=e)

    @abstractmethod
    def _apply(self, state: OntologyState) -> OntologyState:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_args(cls, args: A) -> Self:
        raise NotImplementedError
