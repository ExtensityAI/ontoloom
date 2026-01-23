"""Pydantic response models for the hydra-viz API."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Context(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
    path: Path
