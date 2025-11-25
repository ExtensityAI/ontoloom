from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import (
    ClassName,
    OntologyState,
)
from ontology_hydra.ontology.state.ops.base import (
    BaseOperation,
    BaseOperationArgs,
)
from ontology_hydra.ontology.state.ops.preconditions import Precondition, PresenceRequired
from ontology_hydra.ontology.state.ops.utils import (
    replace_ontology_state,
)


class DeleteClassOperationArgs(BaseOperationArgs):
    """Remove an existing class from the ontology."""

    type: Literal["del_class"] = "del_class"

    name: ClassName = Field(..., description="Name of the class to delete")


class RequiresEmptySubClasses(Precondition):
    """Class must not have subclasses before deletion."""

    class_name: ClassName

    def is_satisfied(self, state: OntologyState) -> bool:
        return state.get_subclasses(self.class_name) == ()


def _create_requirements(args: DeleteClassOperationArgs):
    # Target class must exist and have no subclasses.
    return (
        PresenceRequired(kind="class", name=args.name, exists=True),
        RequiresEmptySubClasses(class_name=args.name),
    )


class DeleteClassOperation(BaseOperation[DeleteClassOperationArgs]):
    def _apply(self, state: OntologyState):
        # TODO also remove class from data and object props
        return replace_ontology_state(
            state, classes=tuple(c for c in state.classes if c.name != self.args.name)
        )

    @classmethod
    def from_args(cls, args: DeleteClassOperationArgs):
        return cls(args, _create_requirements(args))
