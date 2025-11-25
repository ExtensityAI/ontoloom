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


def _create_requirements(args: AddClassOperationArgs):
    # New class must not already exist; parent must be present.
    return (
        RequiresPresence(kind="class", name=args.name, exists=False),
        RequiresPresence(kind="class", name=args.parent, exists=True),
    )


class AddClassOperation(BaseOperation[AddClassOperationArgs]):
    def __init__(self, args: AddClassOperationArgs):
        super().__init__(args, _create_requirements(args))

    def _apply(self, state: OntologyState):
        new_class = Class(
            name=self.args.name,
            parent=self.args.parent,
            description=self.args.description,
        )

        return replace_ontology_state(state, classes=(*state.classes, new_class))
