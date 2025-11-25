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
)
from ontology_hydra.ontology.state.ops.preconditions import PresenceRequired
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


def _create_requirements(args: AddObjectPropertyOperationArgs):
    reqs: list[PresenceRequired] = [
        PresenceRequired(kind="object_property", name=args.name, exists=False),
    ]

    # require all domain classes to exist
    for domain_class in args.domain:
        reqs.append(PresenceRequired(kind="class", name=domain_class, exists=True))

    # require all range classes to exist
    for range_class in args.range:
        reqs.append(PresenceRequired(kind="class", name=range_class, exists=True))

    return tuple(reqs)


class AddObjectPropertyOperation(BaseOperation[AddObjectPropertyOperationArgs]):
    def _apply(self, state: OntologyState):
        new_prop = ObjectProperty(
            name=self.args.name,
            domain=self.args.domain,
            range=self.args.range,
            description=self.args.description,
        )

        return replace_ontology_state(state, object_properties=(*state.object_properties, new_prop))

    @classmethod
    def from_args(cls, args: AddObjectPropertyOperationArgs):
        return cls(args, _create_requirements(args))
