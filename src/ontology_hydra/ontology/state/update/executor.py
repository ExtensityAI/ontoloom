from ontology_hydra.ontology.state.models import OntologyState
from ontology_hydra.ontology.state.update.ops.types import Operation
from ontology_hydra.types import Model


class PendingOp(Model):
    index: int
    operation: Operation


def execute_ops(state: OntologyState, ops: list[Operation]):
    pending = [PendingOp(index=i, operation=op) for i, op in enumerate(ops)]
