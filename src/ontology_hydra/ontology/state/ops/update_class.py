from typing import Literal

from pydantic import Field

from dataclasses import dataclass

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


class UpdateClassOperationArgs(Model):
    """Update an existing class in the ontology."""

    type: Literal["update_class"] = "update_class"

    name: ClassName = Field(..., description="Name of the class to update")

    new_name: ClassName | None = Field(
        None, description="New name for the class (omit if unchanged)"
    )

    new_description: str | None = Field(
        None, description="New description of the class (omit if unchanged)"
    )


def _replace_parent_name_if_required(cls: Class, old_name: ClassName, new_name: ClassName):
    if cls.parent == old_name:
        return Class(
            name=cls.name,
            parent=new_name,
            description=cls.description,
        )

    return cls


def apply_update_class(state: OntologyState, op: UpdateClassOperationArgs):
    target = state.get_class(op.name)

    if target is None:
        return OperationFailure(reason=f"Class '{op.name}' does not exist in the ontology.")

    # TODO: check that name is valid here or somewhere else? probably here is the correct location. DO THIS FOR ALL OPS

    if op.new_name and state.get_class(op.new_name) is not None:
        return OperationFailure(reason=f"Class '{op.new_name}' already exists in the ontology.")

    # update this class
    updated_class = Class(
        name=op.new_name if op.new_name else target.name,
        parent=target.parent,
        description=op.new_description if op.new_description else target.description,
    )

    # update references to this class in other classes' parent fields
    new_classes = tuple(
        _replace_parent_name_if_required(cls, target.name, updated_class.name)
        if cls.name != target.name
        else updated_class
        for cls in state.classes
    )

    return OperationSuccess(state=replace_ontology_state(state, classes=new_classes))


@dataclass(frozen=True, slots=True)
class UpdateClassOperation(BaseOperation[UpdateClassOperationArgs]):
    def requires(self) -> tuple[Requirement, ...]:
        requirements = [Requirement(kind="class", name=self.args.name, exists=True)]
        if self.args.new_name:
            requirements.append(Requirement(kind="class", name=self.args.new_name, exists=False))
        return tuple(requirements)

    def provides(self) -> tuple[Provision, ...]:
        # rename effectively provides the new class name if specified
        if self.args.new_name:
            return (Provision(kind="class", name=self.args.new_name, exists=True),)
        return ()

    def apply(self, state: OntologyState) -> OperationResult:
        return apply_update_class(state, self.args)
