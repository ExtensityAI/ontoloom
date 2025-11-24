from dataclasses import dataclass
from typing import Literal

from ontology_hydra.ontology.state.models import OntologyState


@dataclass(frozen=True, slots=True)
class OperationSuccess:
    state: OntologyState
    success: Literal[True] = True


@dataclass(frozen=True, slots=True)
class OperationFailure:
    reason: str
    success: Literal[False] = False


type OperationResult = OperationSuccess | OperationFailure
