from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import OntologyState, PropertyName
from ontology_hydra.ontology.state.ops.base import (
    BaseOperation,
    BaseOperationArgs,
)
from ontology_hydra.ontology.state.ops.requirements import RequiresPresence
from ontology_hydra.ontology.state.ops.utils import replace_ontology_state


class DeletePropertyOperationArgs(BaseOperationArgs):
    """Remove an existing object/data property from the ontology."""

    type: Literal["del_prop"] = "del_prop"

    name: PropertyName = Field(..., description="Name of the object/data property to delete")


class DeletePropertyOperation(BaseOperation[DeletePropertyOperationArgs]):
    def requires(self):
        return (RequiresPresence(kind="any_property", name=self.args.name, exists=True),)

    def apply(self, state: OntologyState):
        # delete this property
        data_props = tuple(prop for prop in state.data_properties if prop.name != self.args.name)
        object_props = tuple(
            prop for prop in state.object_properties if prop.name != self.args.name
        )

        return replace_ontology_state(
            state, data_properties=data_props, object_properties=object_props
        )
