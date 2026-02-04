"""Shared metric models."""

from pydantic import BaseModel


class Metric(BaseModel):
    """Summary statistics plus raw values for histogramming."""

    min: float
    max: float
    mean: float
    median: float
    stdev: float
    raw: list[float]
