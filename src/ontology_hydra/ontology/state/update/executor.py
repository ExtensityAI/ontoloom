from ontology_hydra.ontology.state.models import OntologyState
from ontology_hydra.ontology.state.update.ops.base import (
    ExceptionFailure,
    Success,
)
from ontology_hydra.ontology.state.update.ops.types import Operation
from ontology_hydra.types import vartuple


def execute_ops(state: OntologyState, ops: vartuple[Operation]):
    for op in ops:
        match op.apply(state):
            case Success() as success:
                state = success.state
            case ExceptionFailure() as failure:
                msg = f"Failed to apply op {op} due to exception: {failure.exception}"
                raise ValueError(msg)

    return state
