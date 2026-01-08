from symai import Expression

from ontology_hydra.ontology.models import Ontology

# TODO: prompt the model with the subset of OWL that we are supporting! remind it of key principles! locality of edit?

_prompt = """You are an ontology engineer extending an existing ontology to better capture a user's domain.

<intent>{intent}</intent>
<ontology>{ontology}</ontology>

Based on the user's intent, propose changes to better model this domain. Describe each proposed change in a short paragraph:
- State the modification (e.g., "Add a Location class with coordinates and address properties")
- Explain what domain concept this captures
- Clarify how this serves the user's stated intent

Write prose, not tables or bullet lists. Focus on the domain concepts implied by the intent."""


def draft_plan(intent: str, ontology: Ontology):
    """Drafts a plan that, when implemented and executed, changes the ontology to better fit user intent."""

    # if this does not work, well enough (low-quality plans), we may want to try to add in more steps to reiterate on the plan and provide more guidance maybe?

    # use raw prompting instead of structured output because we need flexibility and no data structure
    plan: str = Expression.prompt(
        _prompt.format(intent=intent, ontology=ontology.model_dump_json())
    ).value

    return plan
