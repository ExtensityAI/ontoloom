from typing import Literal, cast

from pydantic import Field

from ontology_hydra.ontology.state.models import Class, ClassName, OntologyState
from ontology_hydra.ontology.state.update.effects import ExistenceEffect
from ontology_hydra.ontology.state.update.ops.base import (
    BaseOperation,
    BaseOperationArgs,
)
from ontology_hydra.ontology.state.update.preconditions import ExistencePrecondition
from ontology_hydra.ontology.state.update.resources import ResourceRef
from ontology_hydra.ontology.state.utils import replace_class, replace_ontology_state


class UpdateClassOperationArgs(BaseOperationArgs):
    """Update an existing class in the ontology."""

    type: Literal["update_class"] = "update_class"

    name: ClassName = Field(..., description="Name of the class to update")

    new_name: ClassName | None = Field(
        None, description="New name for the class (omit if unchanged)"
    )

    new_description: str | None = Field(
        None, description="New description of the class (omit if unchanged)"
    )

    # TODO: allow parent reassignment?


def _replace_parent_name_if_required(cls: Class, old_name: ClassName, new_name: ClassName):
    if cls.parent == old_name:
        return Class(
            name=cls.name,
            parent=new_name,
            description=cls.description,
        )

    return cls


def _create_preconditions(args: UpdateClassOperationArgs):
    preconds = [
        ExistencePrecondition(resource=ResourceRef(kind="class", name=args.name), value="existent")
    ]

    # If renaming, the new name must be free.
    if args.new_name:
        preconds.append(
            ExistencePrecondition(
                resource=ResourceRef(kind="class", name=args.new_name), value="non-existent"
            )
        )

    return tuple(preconds)


def _create_effects(args: UpdateClassOperationArgs):
    if not args.new_name:
        # if we are not renaming, there is no relevant effect
        return ()

    return (
        ExistenceEffect(
            resource=ResourceRef(kind="class", name=args.name), value="non-existent"
        ),  # old resource is gone
        ExistenceEffect(
            resource=ResourceRef(kind="class", name=args.new_name), value="existent"
        ),  # new resource exists
    )


class UpdateClassOperation(BaseOperation[UpdateClassOperationArgs]):
    def __init__(self, args: UpdateClassOperationArgs):
        super().__init__(args, _create_preconditions(args), _create_effects(args))

    def _apply(self, state: OntologyState):
        old_class = cast("Class", state.get_class(self.args.name))

        # update the class itself
        updated_class = replace_class(
            old_class,
            name=self.args.new_name or old_class.name,
            description=self.args.new_description or old_class.description,
            parent=old_class.parent,
        )

        # update references to this class in other classes' parent fields
        new_classes = tuple(
            _replace_parent_name_if_required(cls, old_class.name, updated_class.name)
            if cls.name != old_class.name
            else updated_class
            for cls in state.classes
        )

        return replace_ontology_state(state, classes=new_classes)

    @classmethod
    def from_args(cls, args: UpdateClassOperationArgs):
        return cls(args)
