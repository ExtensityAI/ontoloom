from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import Class, ClassName, Model, OntologyState
from ontology_hydra.ontology.state.ops.results import (
    OperationFailure,
    OperationSuccess,
)
from ontology_hydra.ontology.state.ops.utils import replace_ontology_state


class AddClassOperation(Model):
    """Add a new class to the ontology."""

    type: Literal["add_class"] = "add_class"

    name: ClassName = Field(..., description="Name of the class to add")
    parent: ClassName = Field(..., description="Name of parent class")

    description: str = Field(..., description="Description of the class to add")


def apply_add_class(state: OntologyState, op: AddClassOperation):
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
