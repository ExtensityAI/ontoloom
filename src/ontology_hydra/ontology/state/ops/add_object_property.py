from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import (
    ClassName,
    ObjectProperty,
    OntologyState,
    PropertyName,
    vartuple,
)
from ontology_hydra.ontology.state.ops.base import (
    BaseOperation,
    BaseOperationArgs,
    OperationFailure,
    OperationSuccess,
)
from ontology_hydra.ontology.state.ops.requirements import RequiresPresence
from ontology_hydra.ontology.state.ops.utils import replace_ontology_state


class AddObjectPropertyOperationArgs(BaseOperationArgs):
    """Add a new object property to the ontology."""

    type: Literal["add_obj_prop"] = "add_obj_prop"

    name: PropertyName = Field(..., description="Name of the property to add")
    domain: vartuple[ClassName] = Field(
        ..., description="Domain classes for the property"
    )  # TODO: what if domain is both applied to class and it's subclass? is that allowed?
    range: vartuple[ClassName] = Field(..., description="Range classes for the property")

    description: str = Field(..., description="Description of the property to add")


def apply_add_object_property(state: OntologyState, op: AddObjectPropertyOperationArgs):
    if state.get_property(op.name) is not None:
        return OperationFailure(reason=f"Property '{op.name}' already exists in the ontology.")

    # make sure that all domain classes exist
    for domain_class in op.domain:
        if state.get_class(domain_class) is None:
            return OperationFailure(
                reason=f"Domain class '{domain_class}' does not exist in the ontology."
            )

    # make sure that all range classes exist
    for range_class in op.range:
        if state.get_class(range_class) is None:
            return OperationFailure(
                reason=f"Range class '{range_class}' does not exist in the ontology."
            )

    # success!

    new_prop = ObjectProperty(
        name=op.name,
        domain=op.domain,
        range=op.range,
        description=op.description,
    )

    return OperationSuccess(
        state=replace_ontology_state(state, object_properties=(*state.object_properties, new_prop))
    )


class AddObjectPropertyOperation(BaseOperation[AddObjectPropertyOperationArgs]):
    def requires(self):
        base_requirements = (
            RequiresPresence(kind="object_property", name=self.args.name, exists=False),
        )

        domain_requirements = tuple(
            RequiresPresence(kind="class", name=domain_class, exists=True)
            for domain_class in self.args.domain
        )

        range_requirements = tuple(
            RequiresPresence(kind="class", name=range_class, exists=True)
            for range_class in self.args.range
        )

        return base_requirements + domain_requirements + range_requirements

    def _apply(self, state: OntologyState):
        new_prop = ObjectProperty(
            name=self.args.name,
            domain=self.args.domain,
            range=self.args.range,
            description=self.args.description,
        )

        return replace_ontology_state(state, object_properties=(*state.object_properties, new_prop))
