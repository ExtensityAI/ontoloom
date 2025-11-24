from ontology_hydra.ontology.state.models import OntologyState
from ontology_hydra.utils.results import BaseFailure, BaseSuccess


class OperationSuccess(BaseSuccess):
    state: OntologyState


class OperationFailure(BaseFailure):
    reason: str


type OperationResult = OperationSuccess | OperationFailure
