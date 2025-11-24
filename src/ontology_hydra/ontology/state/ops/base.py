from abc import ABC, abstractmethod
from dataclasses import dataclass

from ontology_hydra.ontology.state.models import Model, OntologyState, vartuple
from ontology_hydra.ontology.state.ops.types import OperationArgs
from ontology_hydra.utils.results import BaseFailure, BaseSuccess


class OperationSuccess(BaseSuccess):
    state: OntologyState


class OperationFailure(BaseFailure):
    reason: str


type OperationResult = OperationSuccess | OperationFailure


class Requirement(Model, ABC):
    @abstractmethod
    def test(self, state: OntologyState) -> bool:
        raise NotImplementedError


class Assurance(Model):
    pass


@dataclass(frozen=True, slots=True)
class BaseOperation[A: OperationArgs](ABC):
    args: A

    @abstractmethod
    def requires(self) -> vartuple[Requirement]:
        raise NotImplementedError

    def apply(self, state: OntologyState) -> OperationResult:
        for req in self.requires():
            if not req.test(state):
                return OperationFailure(reason=f"Requirement '{req}' not satisfied.")

        return self._apply(state)

    @abstractmethod
    def _apply(self, state: OntologyState) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    def ensures(self) -> vartuple[Assurance]:
        raise NotImplementedError
