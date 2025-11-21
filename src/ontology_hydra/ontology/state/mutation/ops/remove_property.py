from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import Model, OntologyState, PropertyName
from ontology_hydra.ontology.state.mutation.results import MutationFailed, MutationSucceeded
from ontology_hydra.ontology.state.mutation.utils import replace_ontology_state


class RemovePropertyOperation(Model):
    """Remove an existing object/data property from the ontology."""

    type: Literal["del_prop"] = "del_prop"

    name: PropertyName = Field(..., description="Name of the object/data property to delete")


def remove_property(state: OntologyState, op: RemovePropertyOperation):
    target = state.get_property(op.name)

    if target is None:
        return MutationFailed(reason=f"Property '{op.name}' does not exist in the ontology.")

    # success!

    # remove from appropriate list
    data_props = tuple(prop for prop in state.data_properties if prop.name != target.name)
    object_props = tuple(prop for prop in state.object_properties if prop.name != target.name)

    new_state = replace_ontology_state(
        state, data_properties=data_props, object_properties=object_props
    )

    return MutationSucceeded(state=new_state)
