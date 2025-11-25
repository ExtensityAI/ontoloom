from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import OntologyState, PropertyName
from ontology_hydra.ontology.state.ops.base import (
    BaseOperation,
    BaseOperationArgs,
    OperationFailure,
    OperationResult,
    OperationSuccess,
    Requirement,
)
from ontology_hydra.ontology.state.ops.utils import replace_ontology_state


class DeletePropertyOperationArgs(BaseOperationArgs):
    """Remove an existing object/data property from the ontology."""

    type: Literal["del_prop"] = "del_prop"

    name: PropertyName = Field(..., description="Name of the object/data property to delete")


def apply_delete_property(state: OntologyState, op: DeletePropertyOperationArgs):
    target = state.get_property(op.name)

    if target is None:
        return OperationFailure(reason=f"Property '{op.name}' does not exist in the ontology.")

    # success!

    # remove from appropriate list
    data_props = tuple(prop for prop in state.data_properties if prop.name != target.name)
    object_props = tuple(prop for prop in state.object_properties if prop.name != target.name)

    new_state = replace_ontology_state(
        state, data_properties=data_props, object_properties=object_props
    )

    return OperationSuccess(state=new_state)


class DeletePropertyOperation(BaseOperation[DeletePropertyOperationArgs]):
    def requires(self) -> tuple[Requirement, ...]:
        return (Requirement(kind="property", name=self.args.name, exists=True),)

    def provides(self) -> tuple[Provision, ...]:
        return (
            Provision(kind="data_property", name=self.args.name, exists=False),
            Provision(kind="object_property", name=self.args.name, exists=False),
        )

    def apply(self, state: OntologyState) -> OperationResult:
        return apply_delete_property(state, self.args)
