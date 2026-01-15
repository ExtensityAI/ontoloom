from typing import cast

from pydantic import Field
from symai import Expression
from symai.strategy import contract

from ontology_hydra.ontology.models import Ontology
from ontology_hydra.ontology.revision.executor import OperationFailed, execute_ops
from ontology_hydra.ontology.revision.operations.ops import Operation
from ontology_hydra.utils.schema.llm import DataModel


class _Input(DataModel):
    ontology: Ontology


class OperationSequence(DataModel):
    ops: list[Operation] = Field(
        description="The operations that, when applied, implement the plan."
    )


class DraftExecutionError(Exception):
    """Raised when drafted operations fail to execute."""

    def __init__(self, cause: OperationFailed):
        self.cause = cause
        super().__init__(
            f"Operation {cause.index} ({cause.operation.op}) failed: {cause}"
        )


_prompt = """You are an ontology engineer translating a natural language plan into a sequence of ontology operations.

<intent>{intent}</intent>
<plan>{plan}</plan>
{feedback_section}
Generate operations that implement the plan when applied to the current ontology. For each change described in the plan:
- Choose the appropriate operation type (add_class, add_data_prop, add_object_prop, update_*, delete_*, merge_classes)
- Use exact names from the ontology for existing entities
- Follow naming conventions: PascalCase for classes, camelCase for properties
- Ensure domain/range references point to classes that exist or are created earlier in the sequence

Order operations so dependencies are satisfied: create classes before properties that reference them, parent classes before subclasses.

Return only the operations needed to implement the plan—no more, no less."""

_feedback_template = """<previous_attempt_feedback>
Your previous attempt was rejected. Here's the review:
{feedback}
Address these issues in your new attempt.
</previous_attempt_feedback>"""


@contract(accumulate_errors=True)
class DraftOps(Expression):
    def __init__(
        self,
        plan: str,
        intent: str,
        ontology: Ontology,
        feedback: str | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._plan = plan
        self._intent = intent
        self._ontology = ontology
        self._feedback = feedback

    def forward(self, _: _Input) -> OperationSequence:  # pyright: ignore[reportIncompatibleMethodOverride] # override is correct
        if self.contract_result is None:
            msg = "Contract failed!"
            raise ValueError(msg)

        return self.contract_result

    @property
    def prompt(self):  # pyright: ignore[reportIncompatibleMethodOverride] # override is correct
        feedback_section = (
            _feedback_template.format(feedback=self._feedback) if self._feedback else ""
        )
        return _prompt.format(
            plan=self._plan,
            intent=self._intent,
            feedback_section=feedback_section,
        )


def draft_ops(plan: str, intent: str, ontology: Ontology, feedback: str | None = None):
    drafter = cast("DraftOps", DraftOps(plan, intent, ontology, feedback))
    ops: OperationSequence = drafter(_Input(ontology=ontology))

    # validate by executing - raises DraftExecutionError if ops are invalid
    try:
        execute_ops(ontology, ops.ops)
    except OperationFailed as e:
        raise DraftExecutionError(e) from e

    return ops
