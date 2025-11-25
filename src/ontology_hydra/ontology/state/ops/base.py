from abc import ABC, abstractmethod

from ontology_hydra.ontology.state.models import Model, OntologyState, vartuple
from ontology_hydra.ontology.state.ops.requirements import BaseRequirement
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
    def requires(self) -> vartuple[BaseRequirement]:
        raise NotImplementedError
    
    def apply(self, state: OntologyState) -> OperationResult:
        

    @abstractmethod
    def _apply(self, state: OntologyState) -> OntologyState:
        raise NotImplementedError
