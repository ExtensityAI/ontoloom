from ontology_hydra.ontology.components.implementation.draft_ops import (
    OperationSequence,
    draft_ops,
)
from ontology_hydra.ontology.components.implementation.review_ops import Review, review_ops
from ontology_hydra.ontology.models import Ontology


def implement_plan(
    plan: str,
    intent: str,
    ontology: Ontology,
    max_attempts: int = 5,
) -> tuple[OperationSequence, Review]:
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

    # Return last attempt even if rejected, let caller decide
    assert ops is not None
    assert review is not None
    return ops, review
