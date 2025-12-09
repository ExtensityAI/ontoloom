from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import OntologyState, PropertyName
from ontology_hydra.ontology.state.update.ops.base import BaseOperation
from ontology_hydra.ontology.state.utils import replace_ontology_state


class DeletePropertyOperation(BaseOperation):
    """Removes an existing object/data property from the ontology."""

    type: Literal["del_prop"] = "del_prop"

    name: PropertyName = Field(..., description="Name of the object/data property to delete")

    def _apply(self, state: OntologyState):
        if not state.get_property(self.name):
            raise ValueError(f"Property '{self.name}' does not exist")

        # Remove the property from both lists; only one will actually match.
        data_props = tuple(prop for prop in state.data_properties if prop.name != self.name)
        object_props = tuple(prop for prop in state.object_properties if prop.name != self.name)

        return replace_ontology_state(
            state, data_properties=data_props, object_properties=object_props
        )
