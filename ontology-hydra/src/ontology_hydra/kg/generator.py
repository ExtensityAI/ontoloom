from logging import getLogger
from typing import cast

from symai import Expression
from symai.strategy import LLMDataModel, contract
from tqdm import tqdm

from ontology_hydra.config import ComponentName, HydraConfig
from ontology_hydra.kg.merging import try_merge
from ontology_hydra.kg.schema import DynamicPartialKnowledgeGraph, generate_kg_schema
from ontology_hydra.llm.engine import create_component_engine
from ontology_hydra.ontology.models import Ontology
from ontology_hydra.prompts import prompt_registry
from ontology_hydra.utils.cache import Cache, CacheKey

logger = getLogger("ontology-hydra.kg")


def is_snake_case(s):
    # Must not start or end with underscore
    if not s or s[0] == "_" or s[-1] == "_":
        return False

    # Must not have consecutive underscores
    if "__" in s:
        return False

    # Must only contain lowercase letters, numbers, or underscores
    return all(c.islower() or c.isdigit() or c == "_" for c in s)


def _create_extractor(partial_knowledge_graph_type: type[DynamicPartialKnowledgeGraph]):
    class Input(LLMDataModel):
        texts: list[str]
        kg: partial_knowledge_graph_type  # pyright: ignore[reportInvalidTypeForm] we use this dynamically defined schema here

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
            "graceful": True,
        },
        accumulate_errors=True,
    )
    class Extractor(Expression):
        def __init__(
            self, ontology: Ontology, kg: partial_knowledge_graph_type, *args, **kwargs
        ):  # pyright: ignore[reportInvalidTypeForm] use dynamic type here
            super().__init__(*args, **kwargs)
            self._ontology = ontology
            self._kg = kg

        def forward(self, _: Input) -> partial_knowledge_graph_type:  # pyright: ignore[reportInvalidTypeForm] we again use dynamically defined schema here
            if self.contract_result is None:
                msg = "Contract failed!"
                raise ValueError(msg)
            return self.contract_result

        def pre(self, _: Input) -> bool:
            return True

        def post(self, output: partial_knowledge_graph_type) -> bool:  # pyright: ignore[reportInvalidTypeForm] here too
            # TODO add combination step here (or maybe alternatively in forward? CHECK DOCS! Essentially, in the output, we want to combine all partial entities that have the same name as that simplifies merging)

            # combine output values

            # TODO validate that all object properties are related to the correct ontology classes, i.e. no leo hasParent car (if car is not a Person but a Car and leo is a Person)

            success, issues, merged = try_merge(
                partial_knowledge_graph_type, self._kg, output
            )

            if not success or merged is None:
                raise ValueError(
                    "Some issues occured while merging:" + "\n".join(issues)
                )

            self._kg = merged

            return True

        @property
        def prompt(self):
            return prompt_registry.instruction("triplet_extraction")

        @property
        def kg(self):
            return self._kg

    return Input, cast("Extractor", Extractor)


def generate_kg(
    config: HydraConfig,
    cache: Cache,
    texts: list[str],
    ontology: Ontology | None = None,
    batch_size: int = 1,
    epochs: int = 3,
) -> DynamicPartialKnowledgeGraph:
    partial_json_ck: CacheKey = ("kg", "partial.json")
    partial_html_ck: CacheKey = ("kg", "partial.html")

    if not ontology:
        msg = "For now, ontology must be provided to generate a knowledge graph due to update."
        raise NotImplementedError(msg)

    partial_knowledge_graph = generate_kg_schema(ontology)

    input_model, extractor_type = _create_extractor(partial_knowledge_graph)

    kg = partial_knowledge_graph(data=[])

    extractor = extractor_type(ontology, kg)

    with create_component_engine(config, ComponentName.kg_extractor):
        for i in range(epochs):
            for j in tqdm(
                range(0, len(texts), batch_size), desc=f"Epoch {i + 1}/{epochs}"
            ):
                input_data = input_model(
                    texts=texts[j : j + batch_size],
                    kg=kg,
                )

                logger.debug("KG input: %s", input_data.model_dump_json())

                # TODO annotate output with chunk information!

                _ = extractor(input=input_data)  # pyright: ignore[reportInvalidTypeForm] once again

                kg = extractor.kg

                if cache is not None:
                    cache.write(partial_json_ck, kg.model_dump_json(indent=2))

    if cache is not None:
        cache.write(
            ("kg", "final.json"), kg.model_dump_json(indent=2, exclude_none=True)
        )
        cache.delete(partial_json_ck, partial_html_ck)

    return kg
