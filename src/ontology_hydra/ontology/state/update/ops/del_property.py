from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import OntologyState, PropertyName
from ontology_hydra.ontology.state.update.ops.base import (
    BaseOperation,
    BaseOperationArgs,
)
from ontology_hydra.ontology.state.update.preconditions import (
    exists,
    or_,
)
from ontology_hydra.ontology.state.update.resources import ResourceRef
from ontology_hydra.ontology.state.utils import replace_ontology_state


class DeletePropertyOperationArgs(BaseOperationArgs):
    """Removes an existing object/data property from the ontology."""

    type: Literal["del_prop"] = "del_prop"

    name: PropertyName = Field(..., description="Name of the object/data property to delete")


def _create_preconditions(args: DeletePropertyOperationArgs):
    # Property must exist (data or object).
    return (
        or_(
            exists(
                ResourceRef(kind="data_property", name=args.name),
            ),
            exists(
                ResourceRef(kind="object_property", name=args.name),
            ),
        ),
    )


class DeletePropertyOperation(BaseOperation[DeletePropertyOperationArgs]):
    def __init__(self, args: DeletePropertyOperationArgs):
        super().__init__(args, _create_preconditions(args))

    def _apply(self, state: OntologyState):
        # Remove the property from both lists; only one will actually match.
        data_props = tuple(prop for prop in state.data_properties if prop.name != self.args.name)
        object_props = tuple(
            prop for prop in state.object_properties if prop.name != self.args.name
        )

        return replace_ontology_state(
            state, data_properties=data_props, object_properties=object_props
        )

    @classmethod
    def from_args(cls, args: DeletePropertyOperationArgs):
        return cls(args)
