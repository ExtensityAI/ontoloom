from symai import Expression
from symai.strategy import contract

from ontology_hydra.ontology.models import Ontology
from ontology_hydra.utils.schema.llm import DataModel


class Proposal(DataModel):
    text: str = ""


@contract(post_remedy=False, accumulate_errors=True, verbose=True)
class Test(Expression):
    def __init__(self, intent: str, text: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._intent = intent
        self._text = text

    def forward(self, _: Ontology) -> Proposal:  # pyright: ignore[reportIncompatibleMethodOverride] # this is fine
        if self.contract_result is None:
            msg = "Contract failed!"
            raise ValueError(msg)

        return self.contract_result

    @property
    def prompt(self):  # pyright: ignore[reportIncompatibleMethodOverride] # this is fine
        return (
            "You are an expert ontology engineer. You are given the current state of the ontology as input as well as user intent and a text sample. Your task is to write a simple proposal on how to extend the ontology to better fit (!!!) user intent and (!) the sample text.\n\n"
            f"<intent>{self._intent}</intent>\n\n"
            f"<sample>{self._text}</sample>"
        )
