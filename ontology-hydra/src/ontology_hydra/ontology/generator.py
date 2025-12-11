import logging
from typing import cast

from pydantic import Field
from symai import Expression
from symai.strategy import LLMDataModel, contract
from tqdm import tqdm

from ontology_hydra.ontology.models import Concept, Ontology
from ontology_hydra.ontology.validator import try_add_concepts
from ontology_hydra.prompts import prompt_registry
from ontology_hydra.utils.cache import Cache, CacheKey

# from ontopipe.vis import visualize_ontology

logger = logging.getLogger("ontology-hydra.ontology.generator")


class OntologyGeneratorInput(LLMDataModel):
    cqs: list[str] = Field(
        description="A list of competency questions discovered during an interview process by the ontology engineer. Extract a list of relevant concepts."  # TODO mention that the extracted concepts should be GENERAL but also useful to answer the questions.
    )
    ontology: Ontology = Field(
        description="A dynamic state of the ontology that evolves with each iteration. Use this state to expand the ontology with new concepts."
    )


class OntologyGeneratorOutput(LLMDataModel):
    additions: list[Concept] = Field(
        description="List of new concepts that should be added to the ontology."
    )


# TODO: make sure that properties are not applied to a class and to its superclass (could be autofixed, but rather not have the model generate that. Also, maybe allow moving properties around or EXTENDING properties?)


# =========================================#
# ----Contract-----------------------------#
# =========================================#
@contract(
    pre_remedy=False,
    post_remedy=True,
    verbose=True,
    remedy_retry_params={
        "tries": 25,
        "delay": 0.5,
        "max_delay": 15,
        "jitter": 0.1,
        "backoff": 2,
        "graceful": False,
    },
)
class OntologyGenerator(Expression):
    def __init__(self, ontology: Ontology, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ontology = ontology

    @property
    def prompt(self) -> str:
        return prompt_registry.instruction("ontology_generator")

    def forward(self, _: OntologyGeneratorInput) -> OntologyGeneratorOutput:
        if self.contract_result is None:
            msg = "Contract failed!"
            raise ValueError(msg)
        return self.contract_result

    def pre(self, _: OntologyGeneratorInput):
        return True

    def post(self, output: OntologyGeneratorOutput):
        is_valid, issues = try_add_concepts(self._ontology, output.additions)

        if not is_valid:
            raise ValueError(
                "Ontology validation failed with the following errors:\n- "
                + "\n- ".join(map(str, issues))
            )

        return True


def generate_ontology(
    cqs: list[str], cqs_per_batch: int = 1, cache: Cache | None = None
) -> Ontology:
    # TODO consider providing scope document
    # TODO do this iteratively, i.e. generate until done. Then, critique ontology and regenerate from there.

    ontology = Ontology()
    generator = cast("OntologyGenerator", OntologyGenerator(ontology))

    partial_json_ck: CacheKey = ("ontology", "partial.json")
    partial_html_ck: CacheKey = ("ontology", "partial.html")  # for visualization

    for i in tqdm(range(0, len(cqs), cqs_per_batch)):
        batch_cqs = cqs[i : i + cqs_per_batch]

        generator_input = OntologyGeneratorInput(cqs=batch_cqs, ontology=ontology)

        try:
            _output = generator(input=generator_input)
            # TODO do not like that the ontology is just implicitly mutated here, change this in the future again
        except Exception as e:
            logger.error(f"Error getting state update for batch: {e}")
            continue

        if cache is not None:
            cache.write(partial_json_ck, ontology.model_dump_json(indent=2))

        # visualize_ontology(ontology, partial_html_cache_path, open_browser=False) TODO update

    if cache is not None:
        cache.write(("ontology", "final.json"), ontology.model_dump_json(indent=2))
        cache.delete(partial_json_ck, partial_html_ck)

    logger.debug("Ontology creation completed!")

    return ontology
