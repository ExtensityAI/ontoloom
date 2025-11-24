from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import Model, OntologyState, PropertyName
from ontology_hydra.ontology.state.ops.results import (
    OperationFailure,
    OperationSuccess,
)
from ontology_hydra.ontology.state.ops.utils import replace_ontology_state


class DeletePropertyOperation(Model):
    """Remove an existing object/data property from the ontology."""

    type: Literal["del_prop"] = "del_prop"

    name: PropertyName = Field(..., description="Name of the object/data property to delete")


def apply_delete_property(state: OntologyState, op: DeletePropertyOperation):
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
