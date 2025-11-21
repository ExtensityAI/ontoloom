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
from ontology_hydra.ontology.state.mutation.results import MutationFailed, MutationSucceeded
from ontology_hydra.ontology.state.mutation.utils import replace_ontology_state


class AddDataPropertyOperation(Model):
    """Add a new data property to the ontology."""

    type: Literal["add_data_prop"] = "add_data_prop"

    name: PropertyName = Field(..., description="Name of the property to add")
    domain: vartuple[ClassName] = Field(..., description="Domain classes for the property")
    range: PrimitiveDataType = Field(..., description="Range data types for the property")

    description: str | None = Field(None, description="Description of the property to add")


def add_data_property(state: OntologyState, op: AddDataPropertyOperation):
    if state.get_property(op.name) is not None:
        return MutationFailed(reason=f"Property '{op.name}' already exists in the ontology.")

    # make sure that all domain classes exist
    for domain_class in op.domain:
        if state.get_class(domain_class) is None:
            return MutationFailed(
                reason=f"Domain class '{domain_class}' does not exist in the ontology."
            )

    # success!

    new_prop = DataProperty(
        name=op.name,
        domain=op.domain,
        range=op.range,
        description=op.description or "",
    )

    return MutationSucceeded(
        state=replace_ontology_state(state, data_properties=(*state.data_properties, new_prop))
    )
