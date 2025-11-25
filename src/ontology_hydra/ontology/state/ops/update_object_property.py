from typing import Literal

from pydantic import Field

from dataclasses import dataclass

from ontology_hydra.ontology.state.models import (
    ClassName,
    Model,
    ObjectProperty,
    OntologyState,
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
from ontology_hydra.ontology.state.ops.utils import (
    replace_object_property,
    replace_ontology_state,
)


class UpdateObjectPropertyOperationArgs(Model):
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


def apply_update_object_property(state: OntologyState, op: UpdateObjectPropertyOperationArgs):
    target = state.get_property(op.name)

    if target is None:
        return OperationFailure(reason=f"Property '{op.name}' does not exist in the ontology.")

    # make sure it's an object property
    if not isinstance(target, ObjectProperty):
        return OperationFailure(
            reason=f"Property '{op.name}' is not an object property, but a data property."
        )

    # if changing name, make sure the new name is not already taken
    if op.new_name is not None and state.get_property(op.new_name) is not None:
        return OperationFailure(reason=f"Property '{op.new_name}' already exists in the ontology.")

    # make sure that all domain classes exist
    if op.new_domain is not None:
        for domain_class in op.new_domain:
            if state.get_class(domain_class) is None:
                return OperationFailure(
                    reason=f"Domain class '{domain_class}' does not exist in the ontology."
                )

    # make sure that all range classes exist
    if op.new_range is not None:
        for range_class in op.new_range:
            if state.get_class(range_class) is None:
                return OperationFailure(
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

    return OperationSuccess(state=replace_ontology_state(state, object_properties=remaining_props))


@dataclass(frozen=True, slots=True)
class UpdateObjectPropertyOperation(BaseOperation[UpdateObjectPropertyOperationArgs]):
    def requires(self) -> tuple[Requirement, ...]:
        requirements = [Requirement(kind="object_property", name=self.args.name, exists=True)]

        if self.args.new_name:
            requirements.append(
                Requirement(kind="object_property", name=self.args.new_name, exists=False)
            )
        if self.args.new_domain:
            requirements.extend(
                Requirement(kind="class", name=domain_class, exists=True)
                for domain_class in self.args.new_domain
            )
        if self.args.new_range:
            requirements.extend(
                Requirement(kind="class", name=range_class, exists=True)
                for range_class in self.args.new_range
            )

        return tuple(requirements)

    def provides(self) -> tuple[Provision, ...]:
        if self.args.new_name:
            return (Provision(kind="object_property", name=self.args.new_name, exists=True),)
        return ()

    def apply(self, state: OntologyState) -> OperationResult:
        return apply_update_object_property(state, self.args)
