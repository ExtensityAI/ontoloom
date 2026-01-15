from ontology_hydra.ontology.components.implementation.draft_ops import (
    draft_ops,
)
from ontology_hydra.ontology.components.implementation.review_ops import review_ops
from ontology_hydra.ontology.models import Ontology
from ontology_hydra.ontology.revision.executor import execute_ops


def implement_plan(
    plan: str,
    intent: str,
    ontology: Ontology,
    max_attempts: int = 5,
):
    """Draft and review operations, retrying with feedback on rejection.

    Returns (ops, review, new_ontology) on success.
    """
    assert max_attempts > 0, "Need to allow at least one attempt"

    feedback = None
    ops = None
    review = None

    for _ in range(max_attempts):
        ops = draft_ops(plan, intent, ontology, feedback=feedback)
        review = review_ops(plan, ops, ontology)

        if review.accepted:
            new_ontology = execute_ops(ontology, ops.ops)
            return ops, review, new_ontology

        feedback = review.text

    msg = f"Could not implement plan after {max_attempts} retries. Last review is:\n{review.text if review else '(unknown)'}"
    raise ValueError(msg)
