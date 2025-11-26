from pydantic import BaseModel, ConfigDict
from symai.strategy import LLMDataModel

_cfg = ConfigDict(
    frozen=True,  # immutable by default
    strict=True,  # no extra fields allowed
)


class LLMModel(LLMDataModel):
    model_config = _cfg


class Model(BaseModel):
    model_config = _cfg
