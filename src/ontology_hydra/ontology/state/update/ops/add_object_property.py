from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import (
    ClassName,
    ObjectProperty,
    OntologyState,
    PropertyName,
    vartuple,
)
from ontology_hydra.ontology.state.update.ops.base import (
    BaseOperation,
    BaseOperationArgs,
)
from ontology_hydra.ontology.state.update.preconditions import ExistencePrecondition
from ontology_hydra.ontology.state.update.resources import ResourceRef
from ontology_hydra.ontology.state.utils import replace_ontology_state


class AddObjectPropertyOperationArgs(BaseOperationArgs):
    """Adds a new object property to the ontology."""

    type: Literal["add_obj_prop"] = "add_obj_prop"

    name: PropertyName = Field(..., description="Name of the property to add")
    domain: vartuple[ClassName] = Field(
        ..., description="Domain classes for the property"
    )  # TODO: what if domain is both applied to class and it's subclass? is that allowed?
    range: vartuple[ClassName] = Field(..., description="Range classes for the property")

    description: str = Field(..., description="Description of the property to add")


def _create_preconditions(args: AddObjectPropertyOperationArgs):
    pcs = [
        ExistencePrecondition(
            resource=ResourceRef(kind="object_property", name=args.name), value="non-existent"
        ),
    ]

    # require all domain classes to exist
    pcs += (
        ExistencePrecondition(
            resource=ResourceRef(kind="class", name=domain_class), value="existent"
        )
        for domain_class in args.domain
    )

    # require all range classes to exist
    pcs += (
        ExistencePrecondition(
            resource=ResourceRef(kind="class", name=range_class), value="existent"
        )
        for range_class in args.range
    )

    return tuple(pcs)


class AddObjectPropertyOperation(BaseOperation[AddObjectPropertyOperationArgs]):
    def __init__(
        self,
        args: AddObjectPropertyOperationArgs,
    ):
        super().__init__(args, _create_preconditions(args))

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
        return cls(args)
