from typing import TYPE_CHECKING

from loguru import logger

from ontology_hydra.ontology.components.planning.draft_plan import (
    draft_consolidation_plan,
    draft_plan,
)

if TYPE_CHECKING:
    from ontology_hydra.config import HydraConfig
    from ontology_hydra.ontology.models import Ontology


def generate_plan(
    config: HydraConfig,
    intent: str,
    ontology: Ontology,
    *,
    metrics_summary: str | None = None,
    scope: str | None = None,
):
    """Generates a plan that, when implemented and executed, changes the ontology to better fit user intent."""

    logger.info(
        "Generating plan for intent: {}",
        intent[:80] + "..." if len(intent) > 80 else intent,
    )
    plan = draft_plan(
        config, intent, ontology, metrics_summary=metrics_summary, scope=scope
    )
    logger.info("Plan generated ({} chars)", len(plan))

    return plan


def generate_consolidation_plan(
    config: HydraConfig,
    intent: str,
    ontology: Ontology,
    *,
    metrics_summary: str | None = None,
    scope: str | None = None,
):
    """Generates a consolidation plan that only cleans up the existing ontology."""

    logger.info("Generating consolidation plan")
    plan = draft_consolidation_plan(
        config, intent, ontology, metrics_summary=metrics_summary, scope=scope
    )
    logger.info("Consolidation plan generated ({} chars)", len(plan))

    return plan
