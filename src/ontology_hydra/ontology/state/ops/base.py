from abc import ABC, abstractmethod

from ontology_hydra.ontology.state.models import Model, OntologyState, vartuple
from ontology_hydra.ontology.state.ops.requirements import Requirement
from ontology_hydra.utils.results import BaseFailure, BaseSuccess


class OperationSuccess(BaseSuccess):
    state: OntologyState


class OperationFailure(BaseFailure):
    reason: str


type OperationResult = OperationSuccess | OperationFailure


class BaseOperationArgs(Model):
    pass


class BaseOperation[A: BaseOperationArgs](ABC, Model):
    args: A

    @abstractmethod
    def requires(self) -> vartuple[Requirement]:
        raise NotImplementedError

    @abstractmethod
    def apply(self, state: OntologyState) -> OperationResult:
        raise NotImplementedError
