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
from ontology_hydra.ontology.state.ops.results import (
    OperationFailure,
    OperationSuccess,
)
from ontology_hydra.ontology.state.ops.utils import replace_ontology_state


class AddDataPropertyArgs(Model):
    """Add a new data property to the ontology."""

    type: Literal["add_data_prop"] = "add_data_prop"

    name: PropertyName = Field(..., description="Name of the property")
    domain: vartuple[ClassName] = Field(..., description="Domain classes of the property")
    range: PrimitiveDataType = Field(..., description="Range data type of the property")

    description: str = Field(..., description="Description of the property")


def apply_add_data_property(state: OntologyState, op: AddDataPropertyArgs):
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
