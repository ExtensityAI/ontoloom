from abc import ABC, abstractclassmethod, abstractmethod
from typing import Literal, Self

from ontology_hydra.ontology.state.models import Model, OntologyState, vartuple
from ontology_hydra.ontology.state.ops.requirements import BaseRequirement
from ontology_hydra.utils.results import BaseFailure, BaseSuccess


class Success(BaseSuccess):
    type: Literal[None] = None
    state: OntologyState


class UnsatisfiedRequirementsFailure(BaseFailure):
    type: Literal["unsatisfied_requirements"] = "unsatisfied_requirements"
    unsatisfied_requirements: vartuple[BaseRequirement]


class ExceptionFailure(BaseFailure):
    type: Literal["exception"] = "exception"
    exception: Exception


type Result = Success | UnsatisfiedRequirementsFailure | ExceptionFailure


class BaseOperationArgs(Model):
    pass


class BaseOperation[A: BaseOperationArgs](ABC):
    def __init__(self, args: A, requirements: vartuple[BaseRequirement]):
        self._args = args
        self._requirements = requirements

    @property
    def args(self) -> A:
        return self._args

    @property
    def requirements(self) -> vartuple[BaseRequirement]:
        return self._requirements

    def test_for_unsatisfied_requirements(self, state: OntologyState) -> vartuple[BaseRequirement]:
        """Check for unmet requirements without applying the operation."""
        return tuple(req for req in self._requirements if not req.is_satisfied(state))

    def try_apply(self, state: OntologyState) -> Result:
        unsatisfied_requirements = self.test_for_unsatisfied_requirements(state)

        if len(unsatisfied_requirements) > 0:
            # some requirements are not satisfied, return early and do not apply
            return UnsatisfiedRequirementsFailure(
                unsatisfied_requirements=unsatisfied_requirements,
            )

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
