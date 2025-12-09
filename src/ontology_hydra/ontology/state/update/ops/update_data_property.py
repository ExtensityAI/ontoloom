from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import (
    ClassName,
    OntologyState,
    PrimitiveDataType,
    PropertyName,
    vartuple,
)
from ontology_hydra.ontology.state.update.ops.base import BaseOperation
from ontology_hydra.ontology.state.utils import (
    replace_data_property,
    replace_ontology_state,
)


class UpdateDataPropertyOperation(BaseOperation):
    """Updates an existing data property in the ontology."""

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

    def describe(self):
        changes = list[str]()
        if self.new_name and self.new_name != self.name:
            changes.append(f"name to '{self.new_name}'")
        if self.new_domain and self.new_domain != ():
            changes.append(f"domain to '{', '.join(self.new_domain)}'")
        if self.new_range:
            changes.append(f"range to '{self.new_range}'")
        if self.new_description and self.new_description != "":
            changes.append(f"description to '{self.new_description}'")
        changes_str = " and ".join(changes)
        return f"Update data property '{self.name}': set {changes_str}"

    def _apply(self, state: OntologyState):
        old_prop = state.get_data_property(self.name)
        if not old_prop:
            raise ValueError(f"Data property '{self.name}' does not exist")

        if self.new_name and self.new_name != self.name and state.get_data_property(self.new_name):
            raise ValueError(f"Data property '{self.new_name}' already exists")

        if self.new_domain:
            missing_domain = tuple(cls for cls in self.new_domain if not state.get_class(cls))
            if missing_domain:
                missing = "', '".join(missing_domain)
                raise ValueError(f"Domain class(es) '{missing}' do not exist")

        # update the property itself
        updated_prop = replace_data_property(
            old_prop,
            name=self.new_name or old_prop.name,
            domain=self.new_domain or old_prop.domain,
            range=self.new_range or old_prop.range,
            description=self.new_description or old_prop.description,
        )

        # update the property in the ontology state
        new_props = tuple(
            prop if prop.name != old_prop.name else updated_prop for prop in state.data_properties
        )

        return replace_ontology_state(state, data_properties=new_props)
