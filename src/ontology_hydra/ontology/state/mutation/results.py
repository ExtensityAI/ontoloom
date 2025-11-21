from typing import Literal

from ontology_hydra.ontology.state.models import Model, OntologyState


class MutationSucceeded(Model):
    success: Literal[True] = True
    state: OntologyState


class MutationFailed(Model):
    success: Literal[False] = False
    reason: str
