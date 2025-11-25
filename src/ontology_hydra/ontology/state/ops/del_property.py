from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import OntologyState, PropertyName
from ontology_hydra.ontology.state.ops.base import (
    BaseOperation,
    BaseOperationArgs,
)
from ontology_hydra.ontology.state.ops.requirements import RequiresPresence
from ontology_hydra.ontology.state.ops.utils import replace_ontology_state


class DeletePropertyOperationArgs(BaseOperationArgs):
    """Remove an existing object/data property from the ontology."""

    type: Literal["del_prop"] = "del_prop"

    name: PropertyName = Field(..., description="Name of the object/data property to delete")


def _create_requirements(args: DeletePropertyOperationArgs):
    # Property must exist (data or object).
    return (RequiresPresence(kind="any_property", name=args.name, exists=True),)


class DeletePropertyOperation(BaseOperation[DeletePropertyOperationArgs]):
    def __init__(self, args: DeletePropertyOperationArgs):
        super().__init__(args, _create_requirements(args))

    def _apply(self, state: OntologyState):
        # Remove the property from both lists; only one will actually match.
        data_props = tuple(prop for prop in state.data_properties if prop.name != self.args.name)
        object_props = tuple(
            prop for prop in state.object_properties if prop.name != self.args.name
        )

        return replace_ontology_state(
            state, data_properties=data_props, object_properties=object_props
        )
