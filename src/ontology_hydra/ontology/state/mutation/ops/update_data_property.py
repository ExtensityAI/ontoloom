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
from ontology_hydra.ontology.state.mutation.utils import (
    replace_data_property,
    replace_ontology_state,
)


class UpdateDataPropertyOperation(Model):
    """Update an existing data property in the ontology."""

    type: Literal["update_data_prop"] = "update_data_prop"

    name: PropertyName = Field(..., description="Name of the property to update")

    new_name: PropertyName | None = Field(
        None, description="New name for the property (omit if unchanged)"
    )

    new_domain: vartuple[ClassName] | None = Field(
        None, description="New domain classes for the property (omit if unchanged)"
    )
    new_range: PrimitiveDataType | None = Field(
        None, description="New range data type for the property (omit if unchanged)"
    )

    new_description: str | None = Field(
        None, description="New description of the property (omit if unchanged)"
    )


def update_data_property(state: OntologyState, op: UpdateDataPropertyOperation):
    target = state.get_property(op.name)

    if target is None:
        return MutationFailed(reason=f"Property '{op.name}' does not exist in the ontology.")

    # make sure it's a data property
    if not isinstance(target, DataProperty):
        return MutationFailed(
            reason=f"Property '{op.name}' is not a data property, but an object property."
        )

    # if changing name, make sure the new name is not already taken
    if op.new_name is not None and state.get_property(op.new_name) is not None:
        return MutationFailed(reason=f"Property '{op.new_name}' already exists in the ontology.")

    # make sure that all domain classes exist
    if op.new_domain is not None:
        for domain_class in op.new_domain:
            if state.get_class(domain_class) is None:
                return MutationFailed(
                    reason=f"Domain class '{domain_class}' does not exist in the ontology."
                )

    # success!

    updated_prop = replace_data_property(
        target,
        name=op.new_name or target.name,
        domain=op.new_domain or target.domain,
        range=op.new_range or target.range,
        description=op.new_description or target.description,
    )

    remaining_props = tuple(
        prop if prop.name != target.name else updated_prop for prop in state.data_properties
    )

    return MutationSucceeded(state=replace_ontology_state(state, data_properties=remaining_props))
