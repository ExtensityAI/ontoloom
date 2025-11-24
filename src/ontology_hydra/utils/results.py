from typing import Literal

from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    model_config = ConfigDict(
        frozen=True,  # immutable by default
        strict=True,  # no extra fields allowed
    )


class Failure(Model):
    success: Literal[False] = False


class Success(Model):
    success: Literal[True] = True


type Result = Success | Failure
