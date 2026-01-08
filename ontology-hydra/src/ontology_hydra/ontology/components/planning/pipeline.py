from ontology_hydra.ontology.components.planning.draft_plan import draft_plan
from ontology_hydra.ontology.models import Ontology


def generate_plan(intent: str, ontology: Ontology):
    """Generates a plan that, when implemented and executed, changes the ontology to better fit user intent."""

    return draft_plan(intent, ontology)
