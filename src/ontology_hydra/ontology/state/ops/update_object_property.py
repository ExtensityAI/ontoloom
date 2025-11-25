from typing import Literal, cast

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
)
from ontology_hydra.ontology.state.ops.requirements import RequiresPresence
from ontology_hydra.ontology.state.ops.utils import (
    replace_object_property,
    replace_ontology_state,
)


class UpdateObjectPropertyOperationArgs(BaseOperationArgs):
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


class UpdateObjectPropertyOperation(BaseOperation[UpdateObjectPropertyOperationArgs]):
    def requires(self):  # -> tuple[Any, ...]:
        requirements = [RequiresPresence(kind="object_property", name=self.args.name, exists=True)]

        # if changing name, make sure the new name is not already taken
        if self.args.new_name:
            requirements.append(
                RequiresPresence(kind="object_property", name=self.args.new_name, exists=False)
            )

        # if changing domain, make sure all new domain classes exist
        if self.args.new_domain:
            requirements.extend(
                RequiresPresence(kind="class", name=domain_class, exists=True)
                for domain_class in self.args.new_domain
            )

        # if changing range, make sure all new range classes exist
        if self.args.new_range:
            requirements.extend(
                RequiresPresence(kind="class", name=range_class, exists=True)
                for range_class in self.args.new_range
            )

        return tuple(requirements)

    def apply(self, state: OntologyState):
        old_prop = cast("ObjectProperty", state.get_property(self.args.name))

        # update the property itself
        updated_prop = replace_object_property(
            old_prop,
            name=self.args.new_name or old_prop.name,
            domain=self.args.new_domain or old_prop.domain,
            range=self.args.new_range or old_prop.range,
            description=self.args.new_description or old_prop.description,
        )

        # update the property in the ontology state
        new_props = tuple(
            prop if prop.name != old_prop.name else updated_prop for prop in state.object_properties
        )

        return replace_ontology_state(state, object_properties=new_props)
