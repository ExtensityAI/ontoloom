from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import (
    ClassName,
    DataProperty,
    OntologyState,
    PrimitiveDataType,
    PropertyName,
    vartuple,
)
from ontology_hydra.ontology.state.update.ops.base import BaseOperation
from ontology_hydra.ontology.state.utils import replace_ontology_state


class AddDataPropertyOperation(BaseOperation):
    """Adds a new data property to the ontology."""

    type: Literal["add_data_prop"] = "add_data_prop"

    name: PropertyName = Field(..., description="Name of the property")
    domain: vartuple[ClassName] = Field(..., description="Domain classes of the property")
    range: PrimitiveDataType = Field(..., description="Range data type of the property")
    description: str = Field(..., description="Description of the property")

    def describe(self):
        return f"Add new data property '{self.name}' with domain '{', '.join(self.domain)}', range '{self.range}' and description '{self.description}'"

    def _apply(self, state: OntologyState):
        if state.get_data_property(self.name):
            msg = f"Data property '{self.name}' already exists"
            raise ValueError(msg)

        missing_domain = tuple(cls for cls in self.domain if not state.get_class(cls))
        if missing_domain:
            missing = "', '".join(missing_domain)
            msg = f"Domain class(es) '{missing}' do not exist"
            raise ValueError(msg)

        new_prop = DataProperty(
            name=self.name,
            domain=self.domain,
            range=self.range,
            description=self.description,
        )

        return replace_ontology_state(state, data_properties=(*state.data_properties, new_prop))
