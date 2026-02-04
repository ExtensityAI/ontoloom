from loguru import logger

from ontology_hydra.ontology.components.planning.draft_plan import draft_plan
from ontology_hydra.ontology.models import Ontology


def generate_plan(intent: str, ontology: Ontology):
    """Generates a plan that, when implemented and executed, changes the ontology to better fit user intent."""

    logger.info(
        "Generating plan for intent: {}", intent[:80] + "..." if len(intent) > 80 else intent
    )
    plan = draft_plan(intent, ontology)
    logger.info("Plan generated ({} chars)", len(plan))

    return plan
