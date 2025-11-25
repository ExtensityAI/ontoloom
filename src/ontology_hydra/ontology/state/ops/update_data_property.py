from typing import Literal, cast

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
from ontology_hydra.ontology.state.ops.utils import (
    replace_data_property,
    replace_ontology_state,
)


class UpdateDataPropertyOperationArgs(BaseOperationArgs):
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


class UpdateDataPropertyOperation(BaseOperation[UpdateDataPropertyOperationArgs]):
    def requires(self):
        requirements = [RequiresPresence(kind="data_property", name=self.args.name, exists=True)]

        # if changing name, make sure the new name is not already taken
        if self.args.new_name:
            requirements.append(
                RequiresPresence(kind="data_property", name=self.args.new_name, exists=False)
            )

        # if changing domain, make sure all new domain classes exist
        if self.args.new_domain:
            requirements.extend(
                RequiresPresence(kind="class", name=domain_class, exists=True)
                for domain_class in self.args.new_domain
            )
        return tuple(requirements)

    def apply(self, state: OntologyState):
        old_prop = cast("DataProperty", state.get_property(self.args.name))

        # update the property itself
        updated_prop = replace_data_property(
            old_prop,
            name=self.args.new_name or old_prop.name,
            domain=self.args.new_domain or old_prop.domain,
            range=self.args.new_range or old_prop.range,
            description=self.args.new_description or old_prop.description,
        )

        # update the property in the ontology state
        new_props = tuple(
            prop if prop.name != old_prop.name else updated_prop for prop in state.data_properties
        )

        return replace_ontology_state(state, data_properties=new_props)
