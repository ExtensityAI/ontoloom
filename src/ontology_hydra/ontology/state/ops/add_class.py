from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import Class, ClassName, Model, OntologyState
from ontology_hydra.ontology.state.ops.base import (
    BaseOperation,
    OperationFailure,
    OperationResult,
    OperationSuccess,
    Provision,
    Requirement,
)
from ontology_hydra.ontology.state.ops.utils import replace_ontology_state


class AddClassOperationArgs(Model):
    """Add a new class to the ontology."""

    type: Literal["add_class"] = "add_class"

    name: ClassName = Field(..., description="Name of the class to add")
    parent: ClassName = Field(..., description="Name of parent class")

    description: str = Field(..., description="Description of the class to add")


def apply_add_class(state: OntologyState, op: AddClassOperationArgs):
    if state.get_class(op.name) is not None:
        return OperationFailure(reason=f"Class '{op.name}' already exists in the ontology.")

    parent = state.get_class(op.parent)

    if parent is None:
        return OperationFailure(
            reason=f"Parent class '{op.parent}' does not exist in the ontology."
        )

    # success!

    new_class = Class(
        name=op.name,
        parent=op.parent,
        description=op.description,
    )

    return OperationSuccess(
        state=replace_ontology_state(state, classes=(*state.classes, new_class))
    )


@dataclass(frozen=True, slots=True)
class AddClassOperation(BaseOperation[AddClassOperationArgs]):
    def requires(self) -> tuple[Requirement, ...]:
        return (
            Requirement(kind="class", name=self.args.name, exists=False),
            Requirement(kind="class", name=self.args.parent, exists=True),
        )

    def provides(self) -> tuple[Provision, ...]:
        return (Provision(kind="class", name=self.args.name, exists=True),)

    def apply(self, state: OntologyState) -> OperationResult:
        return apply_add_class(state, self.args)
