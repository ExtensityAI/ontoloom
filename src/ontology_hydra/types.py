from pydantic import BaseModel, ConfigDict
from symai.strategy import LLMDataModel

type vartuple[T] = tuple[T, ...]
"""A tuple of variable length containing elements of type T."""

_cfg = ConfigDict(
    frozen=True,  # immutable by default
    strict=True,  # no extra fields allowed
)


class LLMModel(LLMDataModel):
    model_config = _cfg


class Model(BaseModel):
    model_config = _cfg
