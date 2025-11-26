from ontology_hydra.ontology.state.models import OntologyState
from ontology_hydra.ontology.state.update.ops.types import Operation


def execute_ops(state: OntologyState, ops: list[Operation]):
    # first, detect conflicts among operations