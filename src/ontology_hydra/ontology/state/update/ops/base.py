from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from ontology_hydra.ontology.state.models import OntologyState
from ontology_hydra.types import LLMModel


@dataclass(frozen=True, slots=True)
class Success:
    state: OntologyState
    success: Literal[True] = True
    type: Literal["success"] = "success"


@dataclass(frozen=True, slots=True)
class ExceptionFailure:
    exception: Exception
    success: Literal[False] = False
    type: Literal["exception"] = "exception"


type Result = Success | ExceptionFailure


class BaseOperation(ABC, LLMModel):
    @abstractmethod
    def describe(self) -> str:
        """Provides a human-readable description of the operation."""
        raise NotImplementedError

    @abstractmethod
    def _apply(self, state: OntologyState) -> OntologyState:
        raise NotImplementedError

    def apply(self, state: OntologyState) -> Result:
        try:
            new_state = self._apply(state)
            return Success(state=new_state)
        except Exception as e:
            return ExceptionFailure(exception=e)
