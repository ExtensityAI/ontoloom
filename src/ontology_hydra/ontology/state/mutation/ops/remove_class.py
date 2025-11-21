from typing import Literal, cast

from pydantic import Field

from ontology_hydra.ontology.state.models import (
    ClassName,
    DataProperty,
    Model,
    ObjectProperty,
    OntologyState,
    vartuple,
)
from ontology_hydra.ontology.state.mutation.results import MutationFailed, MutationSucceeded
from ontology_hydra.ontology.state.mutation.utils import (
    replace_data_property,
    replace_object_property,
    replace_ontology_state,
)


class RemoveClassOperation(Model):
    """Remove an existing class from the ontology."""

    type: Literal["del_class"] = "del_class"

    name: ClassName = Field(..., description="Name of the class to delete")


def _remove_class_from_data_property(class_name: ClassName, prop: DataProperty):
    new_domain = tuple(dom for dom in prop.domain if dom != class_name)

    return replace_data_property(prop, domain=new_domain)


def _remove_class_from_object_property(
    class_name: ClassName, prop: ObjectProperty
) -> ObjectProperty:
    new_domain = tuple(dom for dom in prop.domain if dom != class_name)
    new_range = tuple(rng for rng in prop.range if rng != class_name)

    return replace_object_property(prop, domain=new_domain, range=new_range)


def remove_class(state: OntologyState, op: RemoveClassOperation):
    if (target := state.get_class(op.name)) is None:
        return MutationFailed(reason=f"Class '{op.name}' does not exist in the ontology.")

    # we also need to remove all subclasses recursively
    subclasses = state.get_subclasses(target.name)

    for subclass in subclasses:
        # implicitly create a remove op for the subclass and recursively remove it
        result = remove_class(
            state,
            RemoveClassOperation(name=subclass.name),
        )

        if isinstance(result, MutationFailed):
            # TODO: improve error here, though this should never happen. we want to provide better context on which operation originated this error
            return result

        # update state, it is now without the subclass
        state = result.state

        # TODO: also consider that at some point, some properties might have NO DOMAIN/RANGE left, we definitely want to penalize this in the judge

    # remove from classes
    new_classes = tuple(c for c in state.classes if c != target)

    # remove from domain and range in obj props
    new_object_properties = cast(
        "vartuple[ObjectProperty]",
        tuple(
            _remove_class_from_object_property(target.name, prop)
            for prop in state.object_properties
        ),
    )

    # remove from domain in data props
    new_data_properties = cast(
        "vartuple[DataProperty]",
        tuple(
            _remove_class_from_data_property(target.name, prop) for prop in state.data_properties
        ),
    )

    return MutationSucceeded(
        state=replace_ontology_state(
            state,
            classes=new_classes,
            object_properties=new_object_properties,
            data_properties=new_data_properties,
        )
    )
