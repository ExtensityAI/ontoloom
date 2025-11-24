from collections.abc import Callable

from ontology_hydra.ontology.state.models import OntologyState
from ontology_hydra.ontology.state.mutation.ops.add_class import AddClassOperation, apply_add_class
from ontology_hydra.ontology.state.mutation.ops.add_data_property import (
    AddDataPropertyOperation,
    apply_add_data_property,
)
from ontology_hydra.ontology.state.mutation.ops.add_object_property import (
    AddObjectPropertyOperation,
    apply_add_object_property,
)
from ontology_hydra.ontology.state.mutation.ops.del_class import (
    DeleteClassOperation,
    apply_delete_class,
)
from ontology_hydra.ontology.state.mutation.ops.results import OperationResult
from ontology_hydra.ontology.state.mutation.ops.types import Operation
from ontology_hydra.ontology.state.mutation.ops.update_class import (
    UpdateClassOperation,
    apply_update_class,
)
from ontology_hydra.ontology.state.mutation.ops.update_data_property import (
    UpdateDataPropertyOperation,
    apply_update_data_property,
)
from ontology_hydra.ontology.state.mutation.ops.update_object_property import (
    UpdateObjectPropertyOperation,
    apply_update_object_property,
)


def _extract_ops_of_type[T: Operation](ops: list[Operation], op_type: type[T]):
    return (
        [op for op in ops if isinstance(op, op_type)],
        [op for op in ops if not isinstance(op, op_type)],
    )


def apply_ops_of_type[T: Operation](
    state: OntologyState,
    ops: list[Operation],
    op_type: type[T],
    apply: Callable[[OntologyState, T], OperationResult],
):
    ops_of_type, remaining_ops = _extract_ops_of_type(ops, op_type)

    for op in ops_of_type:
        result = apply(state, op)

        if result.success is True:
            state = result.state

    return state, remaining_ops


def apply(state: OntologyState, ops: list[Operation]) -> OntologyState:
    # first delete properties as nothing depends on them and they might be recreated by the model again
    state, ops = apply_ops_of_type(state, ops, DeleteClassOperation, apply_delete_class)

    # next delete classes as they might be recreated by the model again
    state, ops = apply_ops_of_type(state, ops, DeleteClassOperation, apply_delete_class)

    # finally add classes as other operations might depend on them
    state, ops = apply_ops_of_type(state, ops, AddClassOperation, apply_add_class)

    state, ops = apply_ops_of_type(state, ops, AddDataPropertyOperation, apply_add_data_property)
    state, ops = apply_ops_of_type(
        state, ops, AddObjectPropertyOperation, apply_add_object_property
    )

    state, ops = apply_ops_of_type(state, ops, UpdateClassOperation, apply_update_class)
    state, ops = apply_ops_of_type(
        state, ops, UpdateDataPropertyOperation, apply_update_data_property
    )
    state, ops = apply_ops_of_type(
        state, ops, UpdateObjectPropertyOperation, apply_update_object_property
    )

    return state
