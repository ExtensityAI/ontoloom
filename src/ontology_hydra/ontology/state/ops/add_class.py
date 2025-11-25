from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import Class, ClassName, OntologyState
from ontology_hydra.ontology.state.ops.base import (
    BaseOperation,
    BaseOperationArgs,
)
from ontology_hydra.ontology.state.ops.effects import PresenceEffect
from ontology_hydra.ontology.state.ops.preconditions import PresencePrecondition
from ontology_hydra.ontology.state.ops.resources import ResourceRef
from ontology_hydra.ontology.state.ops.utils import replace_ontology_state


class AddClassOperationArgs(BaseOperationArgs):
    """Add a new class to the ontology."""

    type: Literal["add_class"] = "add_class"

    name: ClassName = Field(..., description="Name of the class to add")
    parent: ClassName = Field(..., description="Name of parent class")

    description: str = Field(..., description="Description of the class to add")


def _create_preconditions(args: AddClassOperationArgs):
    return (
        PresencePrecondition(
            resource=ResourceRef(kind="class", name=args.name), value="absent"
        ),  # new class must not exist yet
        PresencePrecondition(
            resource=ResourceRef(kind="class", name=args.parent), value="present"
        ),  # parent class must exist
    )


def _create_effects(args: AddClassOperationArgs):
    return (
        PresenceEffect(
            resource=ResourceRef(kind="class", name=args.name), value="present"
        ),  # creates new class
    )


class AddClassOperation(BaseOperation[AddClassOperationArgs]):
    def __init__(
        self,
        args: AddClassOperationArgs,
    ):
        super().__init__(args, _create_preconditions(args), _create_effects(args))

    def _apply(self, state: OntologyState):
        new_class = Class(
            name=self.args.name,
            parent=self.args.parent,
            description=self.args.description,
        )

        return replace_ontology_state(state, classes=(*state.classes, new_class))

    @classmethod
    def from_args(cls, args: AddClassOperationArgs):
        return cls(args)
