from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import (
    ClassName,
    OntologyState,
)
from ontology_hydra.ontology.state.update.effects import ExistenceEffect
from ontology_hydra.ontology.state.update.ops.base import (
    BaseOperation,
    BaseOperationArgs,
)
from ontology_hydra.ontology.state.update.preconditions import ExistencePrecondition, Precondition
from ontology_hydra.ontology.state.update.resources import ResourceRef
from ontology_hydra.ontology.state.utils import (
    replace_ontology_state,
)


class DeleteClassOperationArgs(BaseOperationArgs):
    """Remove an existing class from the ontology."""

    type: Literal["del_class"] = "del_class"

    name: ClassName = Field(..., description="Name of the class to delete")


class HasNoSubClassesPrecondition(Precondition):
    """Class must not have subclasses before deletion."""

    class_name: ClassName

    def is_satisfied(self, state: OntologyState) -> bool:
        return state.get_subclasses(self.class_name) == ()


def _create_preconditions(args: DeleteClassOperationArgs):
    return (
        ExistencePrecondition(
            resource=ResourceRef(kind="class", name=args.name), value="existent"
        ),  # target class must exist
        HasNoSubClassesPrecondition(class_name=args.name),  # target class must have no subclasses
    )


def _create_effects(args: DeleteClassOperationArgs):
    return (
        ExistenceEffect(
            resource=ResourceRef(kind="class", name=args.name), value="non-existent"
        ),  # deletes the class
    )


class DeleteClassOperation(BaseOperation[DeleteClassOperationArgs]):
    def __init__(self, args: DeleteClassOperationArgs):
        super().__init__(args, _create_preconditions(args), _create_effects(args))

    def _apply(self, state: OntologyState):
        # TODO also remove class from data and object props
        return replace_ontology_state(
            state, classes=tuple(c for c in state.classes if c.name != self.args.name)
        )

    @classmethod
    def from_args(cls, args: DeleteClassOperationArgs):
        return cls(args)
