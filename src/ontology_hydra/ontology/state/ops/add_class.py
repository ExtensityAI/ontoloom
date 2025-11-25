from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import Class, ClassName, OntologyState
from ontology_hydra.ontology.state.ops.base import (
    BaseOperation,
    BaseOperationArgs,
)
from ontology_hydra.ontology.state.ops.requirements import RequiresPresence
from ontology_hydra.ontology.state.ops.utils import replace_ontology_state


class AddClassOperationArgs(BaseOperationArgs):
    """Add a new class to the ontology."""

    type: Literal["add_class"] = "add_class"

    name: ClassName = Field(..., description="Name of the class to add")
    parent: ClassName = Field(..., description="Name of parent class")

    description: str = Field(..., description="Description of the class to add")


class AddClassOperation(BaseOperation[AddClassOperationArgs]):
    def requires(self):
        return (
            RequiresPresence(kind="class", name=self.args.name, exists=False),
            RequiresPresence(kind="class", name=self.args.parent, exists=True),
        )

    def _apply(self, state: OntologyState):
        new_class = Class(
            name=self.args.name,
            parent=self.args.parent,
            description=self.args.description,
        )

        return replace_ontology_state(state, classes=(*state.classes, new_class))
