from ontology_hydra.ontology.state.models import OntologyState
from ontology_hydra.utils.results import Failure, Success


class OperationSuccess(Success):
    state: OntologyState


class OperationFailure(Failure):
    reason: str


type OperationResult = OperationSuccess | OperationFailure
