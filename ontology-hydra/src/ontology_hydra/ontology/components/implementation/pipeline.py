from ontology_hydra.ontology.components.implementation.draft_ops import (
    draft_ops,
)
from ontology_hydra.ontology.components.implementation.review_ops import review_ops
from ontology_hydra.ontology.models import Ontology


def implement_plan(
    plan: str,
    intent: str,
    ontology: Ontology,
    max_attempts: int = 5,
):
    """Draft and review operations, retrying with feedback on rejection."""

    assert max_attempts > 0, "Need to allow at least one attempt"

    feedback = None
    ops = None
    review = None

    for _ in range(max_attempts):
        ops = draft_ops(plan, intent, ontology, feedback=feedback)
        review = review_ops(plan, ops, ontology)

        if review.accepted:
            return ops, review

        feedback = review.text

    msg = f"Could not implement plan after {max_attempts} retries. Last review is:\n{review.text if review else '(unknown)'}"
    raise ValueError(msg)
