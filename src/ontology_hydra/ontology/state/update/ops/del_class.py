from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import ClassName, OntologyState
from ontology_hydra.ontology.state.update.ops.base import BaseOperation
from ontology_hydra.ontology.state.utils import replace_ontology_state


class DeleteClassOperation(BaseOperation):
    """Removes an existing class from the ontology."""

    type: Literal["del_class"] = "del_class"

    name: ClassName = Field(..., description="Name of the class to delete")

    def describe(self):
        return f"Delete class '{self.name}'"

    def _apply(self, state: OntologyState):
        if not state.get_class(self.name):
            msg = f"Class '{self.name}' does not exist"
            raise ValueError(msg)

        if state.get_subclasses(self.name):
            msg = f"Class '{self.name}' has subclasses and cannot be deleted"
            raise ValueError(msg)

        # TODO also remove class from data and object props
        return replace_ontology_state(
            state, classes=tuple(c for c in state.classes if c.name != self.name)
        )
