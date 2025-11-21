from ontology_hydra.ontology.agents.proposer.ops.classes import AddClassOperation
from ontology_hydra.ontology.agents.proposer.proposer import Proposal
from ontology_hydra.ontology.models import OntologyState


def apply_proposal(state: OntologyState, proposal: Proposal):
    # first, try to add classes as they might be needed for properties and adding classes does not break anything

    add_class_ops = proposal.get_ops_of_type(AddClassOperation)

    for op in add_class_ops:
