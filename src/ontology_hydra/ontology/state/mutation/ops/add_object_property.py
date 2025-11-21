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
from ontology_hydra.ontology.state.mutation.utils import replace_ontology_state


class AddObjectPropertyOperation(Model):
    """Add a new object property to the ontology."""

    type: Literal["add_obj_prop"] = "add_obj_prop"

    name: PropertyName = Field(..., description="Name of the property to add")
    domain: vartuple[ClassName] = Field(
        ..., description="Domain classes for the property"
    )  # TODO: what if domain is both applied to class and it's subclass? is that allowed?
    range: vartuple[ClassName] = Field(..., description="Range classes for the property")

    description: str | None = Field(None, description="Description of the property to add")


def add_object_property(state: OntologyState, op: AddObjectPropertyOperation):
    if state.get_property(op.name) is not None:
        return MutationFailed(reason=f"Property '{op.name}' already exists in the ontology.")

    # make sure that all domain classes exist
    for domain_class in op.domain:
        if state.get_class(domain_class) is None:
            return MutationFailed(
                reason=f"Domain class '{domain_class}' does not exist in the ontology."
            )

    # make sure that all range classes exist
    for range_class in op.range:
        if state.get_class(range_class) is None:
            return MutationFailed(
                reason=f"Range class '{range_class}' does not exist in the ontology."
            )

    # success!

    new_prop = ObjectProperty(
        name=op.name,
        domain=op.domain,
        range=op.range,
        description=op.description or "",
    )

    return MutationSucceeded(
        state=replace_ontology_state(state, object_properties=(*state.object_properties, new_prop))
    )
