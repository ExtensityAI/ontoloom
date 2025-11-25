from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import (
    ClassName,
    DataProperty,
    Model,
    OntologyState,
    PrimitiveDataType,
    PropertyName,
    vartuple,
)
from ontology_hydra.ontology.state.ops.base import (
    BaseOperation,
    OperationFailure,
    OperationResult,
    OperationSuccess,
    Provision,
    Requirement,
)
from ontology_hydra.ontology.state.ops.utils import replace_ontology_state


class AddDataPropertyOperationArgs(Model):
    """Add a new data property to the ontology."""

    type: Literal["add_data_prop"] = "add_data_prop"

    name: PropertyName = Field(..., description="Name of the property")
    domain: vartuple[ClassName] = Field(..., description="Domain classes of the property")
    range: PrimitiveDataType = Field(..., description="Range data type of the property")

    description: str = Field(..., description="Description of the property")


def apply_add_data_property(state: OntologyState, op: AddDataPropertyOperationArgs):
    if state.get_property(op.name) is not None:
        return OperationFailure(reason=f"Property '{op.name}' already exists in the ontology.")

    # make sure that all domain classes exist
    for domain_class in op.domain:
        if state.get_class(domain_class) is None:
            return OperationFailure(
                reason=f"Domain class '{domain_class}' does not exist in the ontology."
            )

    # success!

    new_prop = DataProperty(
        name=op.name,
        domain=op.domain,
        range=op.range,
        description=op.description,
    )

    return OperationSuccess(
        state=replace_ontology_state(state, data_properties=(*state.data_properties, new_prop))
    )


class AddDataPropertyOperation(BaseOperation[AddDataPropertyOperationArgs]):
    def requires(self):
        base_requirements = (Requirement(kind="data_property", name=self.args.name, exists=False),)
        domain_requirements = tuple(
            Requirement(kind="class", name=domain_class, exists=True)
            for domain_class in self.args.domain
        )
        return base_requirements + domain_requirements

    def provides(self):
        return (Provision(kind="data_property", name=self.args.name, exists=True),)

    def apply(self, state: OntologyState):
        return apply_add_data_property(state, self.args)
