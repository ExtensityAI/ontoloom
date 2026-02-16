from typing import TYPE_CHECKING

from loguru import logger

from ontology_hydra.ontology.components.implementation.draft_ops import draft_ops
from ontology_hydra.ontology.components.implementation.review_ops import review_ops
from ontology_hydra.ontology.components.implementation.revise_ops import revise_ops
from ontology_hydra.ontology.revision.executor import execute_ops

if TYPE_CHECKING:
    from ontology_hydra.config import HydraConfig
    from ontology_hydra.ontology.models import Ontology


def implement_plan(
    config: HydraConfig,
    plan: str,
    intent: str,
    ontology: Ontology,
    max_attempts: int = 5,
):
    """Draft and review operations, retrying with feedback on rejection.

    Returns (ops, review, new_ontology) on success.
    """
    assert max_attempts > 0, "Need to allow at least one attempt"

    logger.info("Implementing plan (max {} attempts)", max_attempts)

    ops = None
    review = None

    for attempt in range(max_attempts):
        if ops is None:
            logger.info("Attempt {}/{}: drafting operations", attempt + 1, max_attempts)
            ops = draft_ops(config, plan, intent, ontology)
        else:
            logger.info("Attempt {}/{}: revising operations", attempt + 1, max_attempts)
            ops = revise_ops(config, plan, intent, ontology, ops, feedback=review.text)
        logger.debug("Got {} operations", len(ops.ops))

        logger.info("Reviewing operations")
        review = review_ops(config, plan, ops, ontology, intent=intent)

        if review.accepted:
            logger.info("Review accepted, executing {} operations", len(ops.ops))
            new_ontology = execute_ops(ontology, ops.ops)
            return ops, review, new_ontology

        logger.warning("Review rejected (attempt {}/{})", attempt + 1, max_attempts)

    msg = f"Could not implement plan after {max_attempts} retries. Last review is:\n{review.text if review else '(unknown)'}"
    logger.error("Implementation failed: {}", msg)
    raise ValueError(msg)
