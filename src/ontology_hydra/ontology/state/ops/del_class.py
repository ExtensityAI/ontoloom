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
from ontology_hydra.ontology.state.ops.requirements import BaseRequirement, RequiresPresence
from ontology_hydra.ontology.state.ops.utils import (
    replace_ontology_state,
)


class DeleteClassOperationArgs(BaseOperationArgs):
    """Remove an existing class from the ontology."""

    type: Literal["del_class"] = "del_class"

    name: ClassName = Field(..., description="Name of the class to delete")


class RequiresEmptySubClasses(BaseRequirement):
    """"""

    class_name: ClassName

    def is_satisfied(self, state: OntologyState) -> bool:
        return state.get_subclasses(self.class_name) == ()


class DeleteClassOperation(BaseOperation[DeleteClassOperationArgs]):
    def requires(self):
        return (
            RequiresPresence(kind="class", name=self.args.name, exists=True),
            RequiresEmptySubClasses(class_name=self.args.name),
        )

    def apply(self, state: OntologyState):
        # TODO also remove class from data and object props
        return replace_ontology_state(
            state, classes=tuple(c for c in state.classes if c.name != self.args.name)
        )
