from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import Class, ClassName, OntologyState
from ontology_hydra.ontology.state.update.ops.base import BaseOperation
from ontology_hydra.ontology.state.utils import replace_ontology_state


class AddClassOperation(BaseOperation):
    """Adds a new class to the ontology."""

    type: Literal["add_class"] = "add_class"

    name: ClassName = Field(..., description="Name of the class to add")
    parent: ClassName = Field(..., description="Name of parent class")
    description: str = Field(..., description="Description of the class to add")

    def describe(self):
        return f"Add new class '{self.name}' with parent '{self.parent}' and description '{self.description}'"

    def _apply(self, state: OntologyState):
        if state.get_class(self.name):
            msg = f"Class '{self.name}' already exists"
            raise ValueError(msg)

        if not state.get_class(self.parent):
            msg = f"Parent class '{self.parent}' does not exist"
            raise ValueError(msg)

        new_class = Class(
            name=self.name,
            parent=self.parent,
            description=self.description,
        )

        return replace_ontology_state(state, classes=(*state.classes, new_class))
