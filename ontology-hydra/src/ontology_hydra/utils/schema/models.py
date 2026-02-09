from functools import lru_cache

from pydantic import ConfigDict
from symai.strategy import LLMDataModel

from ontology_hydra.utils.schema.formatting import format_schema
from ontology_hydra.utils.schema.generation import schema_from_model


class DataModel(LLMDataModel):
    model_config = ConfigDict(strict=True)

    @classmethod
    @lru_cache
    def to_schema(cls):
        # TODO: cache? make it a property?
        return schema_from_model(cls)

    @classmethod
    def to_formatted_schema(cls):
        return format_schema(cls.to_schema())

    @classmethod
    @lru_cache
    def instruct_llm(cls):
        return cls.to_formatted_schema()

    @classmethod
    @lru_cache
    def simplify_json_schema(cls):
        return cls.to_formatted_schema()  # TODO: consider omitting - maybe the LLM can infer it from the provided inputs / maybe it does not need the input data model? but: descriptions are useful!
