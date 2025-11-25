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
from ontology_hydra.ontology.state.ops.base import (
    BaseOperation,
    BaseOperationArgs,
)
from ontology_hydra.ontology.state.ops.requirements import RequiresPresence
from ontology_hydra.ontology.state.ops.utils import replace_ontology_state


class AddDataPropertyOperationArgs(BaseOperationArgs):
    """Add a new data property to the ontology."""

    type: Literal["add_data_prop"] = "add_data_prop"

    name: PropertyName = Field(..., description="Name of the property")
    domain: vartuple[ClassName] = Field(..., description="Domain classes of the property")
    range: PrimitiveDataType = Field(..., description="Range data type of the property")

    description: str = Field(..., description="Description of the property")


class AddDataPropertyOperation(BaseOperation[AddDataPropertyOperationArgs]):
    def requires(self):
        base_requirements = (
            RequiresPresence(kind="data_property", name=self.args.name, exists=False),
        )

        domain_requirements = tuple(
            RequiresPresence(kind="class", name=domain_class, exists=True)
            for domain_class in self.args.domain
        )

        return base_requirements + domain_requirements

    def _apply(self, state: OntologyState):
        new_prop = DataProperty(
            name=self.args.name,
            domain=self.args.domain,
            range=self.args.range,
            description=self.args.description,
        )

        return replace_ontology_state(state, data_properties=(*state.data_properties, new_prop))
