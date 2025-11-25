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


def _create_requirements(args: UpdateObjectPropertyOperationArgs):
    reqs: list[RequiresPresence] = [
        RequiresPresence(kind="object_property", name=args.name, exists=True)
    ]

    # If renaming, the new name must be free.
    if args.new_name:
        reqs.append(RequiresPresence(kind="object_property", name=args.new_name, exists=False))

    # If changing domain/range, ensure referenced classes exist.
    if args.new_domain:
        reqs.extend(
            RequiresPresence(kind="class", name=domain_class, exists=True)
            for domain_class in args.new_domain
        )

    if args.new_range:
        reqs.extend(
            RequiresPresence(kind="class", name=range_class, exists=True)
            for range_class in args.new_range
        )

    return tuple(reqs)


class UpdateObjectPropertyOperation(BaseOperation[UpdateObjectPropertyOperationArgs]):
    def _apply(self, state: OntologyState):
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

    @classmethod
    def from_args(cls, args: UpdateObjectPropertyOperationArgs):
        return cls(args, _create_requirements(args))
