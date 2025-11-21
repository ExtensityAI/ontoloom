from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import (
    ClassName,
    Model,
    ObjectProperty,
    OntologyState,
    PropertyName,
    vartuple,
)
from ontology_hydra.ontology.state.mutation.results import MutationFailed, MutationSucceeded
from ontology_hydra.ontology.state.mutation.utils import (
    replace_object_property,
    replace_ontology_state,
)


class UpdateObjectPropertyOperation(Model):
    """Update an existing object property in the ontology."""

    type: Literal["update_obj_prop"] = "update_obj_prop"

    name: PropertyName = Field(..., description="Name of the property to update")

    new_name: PropertyName | None = Field(
        None, description="New name for the property (omit if unchanged)"
    )
    new_domain: vartuple[ClassName] | None = Field(
        None, description="New domain classes for the property (omit if unchanged)"
    )
    new_range: vartuple[ClassName] | None = Field(
        None, description="New range classes for the property (omit if unchanged)"
    )

    new_description: str | None = Field(
        None, description="New description of the property (omit if unchanged)"
    )


def update_object_property(state: OntologyState, op: UpdateObjectPropertyOperation):
    target = state.get_property(op.name)

    if target is None:
        return MutationFailed(reason=f"Property '{op.name}' does not exist in the ontology.")

    # make sure it's an object property
    if not isinstance(target, ObjectProperty):
        return MutationFailed(
            reason=f"Property '{op.name}' is not an object property, but a data property."
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

    # make sure that all range classes exist
    if op.new_range is not None:
        for range_class in op.new_range:
            if state.get_class(range_class) is None:
                return MutationFailed(
                    reason=f"Range class '{range_class}' does not exist in the ontology."
                )

    # success!

    updated_prop = replace_object_property(
        target,
        name=op.new_name or target.name,
        domain=op.new_domain or target.domain,
        range=op.new_range or target.range,
        description=op.new_description or target.description,
    )

    remaining_props = tuple(
        prop if prop.name != target.name else updated_prop for prop in state.object_properties
    )

    return MutationSucceeded(state=replace_ontology_state(state, object_properties=remaining_props))
