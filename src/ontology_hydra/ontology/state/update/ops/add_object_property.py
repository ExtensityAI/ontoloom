from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import (
    ClassName,
    ObjectProperty,
    OntologyState,
    PropertyName,
    vartuple,
)
from ontology_hydra.ontology.state.update.ops.base import BaseOperation
from ontology_hydra.ontology.state.utils import replace_ontology_state


class AddObjectPropertyOperation(BaseOperation):
    """Adds a new object property to the ontology."""

    type: Literal["add_obj_prop"] = "add_obj_prop"

    name: PropertyName = Field(..., description="Name of the property to add")
    domain: vartuple[ClassName] = Field(
        ..., description="Domain classes for the property"
    )  # TODO: what if domain is both applied to class and it's subclass? is that allowed?
    range: vartuple[ClassName] = Field(..., description="Range classes for the property")
    description: str = Field(..., description="Description of the property to add")

    def describe(self):
        return f"Add new object property '{self.name}' with domain '{', '.join(self.domain)}', range '{', '.join(self.range)}' and description '{self.description}'"

    def _apply(self, state: OntologyState):
        if state.get_object_property(self.name):
            msg = f"Object property '{self.name}' already exists"
            raise ValueError(msg)

        missing_domain = tuple(cls for cls in self.domain if not state.get_class(cls))
        if missing_domain:
            missing = "', '".join(missing_domain)
            msg = f"Domain class(es) '{missing}' do not exist"
            raise ValueError(msg)

        missing_range = tuple(cls for cls in self.range if not state.get_class(cls))
        if missing_range:
            missing = "', '".join(missing_range)
            msg = f"Range class(es) '{missing}' do not exist"
            raise ValueError(msg)

        new_prop = ObjectProperty(
            name=self.name,
            domain=self.domain,
            range=self.range,
            description=self.description,
        )

        return replace_ontology_state(state, object_properties=(*state.object_properties, new_prop))
