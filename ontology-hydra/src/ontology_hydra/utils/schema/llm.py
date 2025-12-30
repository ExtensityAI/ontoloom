from pydantic import ConfigDict
from symai.strategy import LLMDataModel

from ontology_hydra.utils.schema.formatting import format_schema
from ontology_hydra.utils.schema.generation import schema_from_model


class DataModel(LLMDataModel):
    model_config = ConfigDict(strict=True)

    @classmethod
    def to_schema(cls):
        # TODO: cache? make it a property?
        return schema_from_model(cls)

    @classmethod
    def to_formatted_schema(cls):
        return format_schema(cls.to_schema())
