from pathlib import Path

from ontology_hydra.metrics.structural import StructuralMetrics
from ontology_hydra.ontology.models import Ontology
from ontology_hydra.ontology.revision.operations import Operation
from ontology_hydra.ontology.run import RunMetadata
from pydantic import BaseModel, Field


class IterationSummary(BaseModel):
    """Summary of a single iteration within a run."""

    index: int
    has_ontology: bool
    has_ops: bool
    has_plan: bool
    has_review: bool
    metrics: StructuralMetrics | None = None


class IterationDetail(BaseModel):
    """Full data for a single iteration."""

    index: int
    ontology: Ontology | None = None
    ops: list[Operation] = []
    plan: str | None = None
    review: str | None = None
    metrics: StructuralMetrics | None = None


class MetricsTimeSeriesPoint(BaseModel):
    """A single point in the metrics time series."""

    iteration: int
    metrics: StructuralMetrics


class MetricsTimeSeries(BaseModel):
    """Metrics over all iterations for a run."""

    name: str
    points: list[MetricsTimeSeriesPoint]


class Run(BaseModel):
    """Runtime model — dir is discovered, metadata loaded from dir/run.json."""

    dir: Path = Field(exclude=True)
    metadata: RunMetadata


class RunDetail(Run):
    """Detailed view of a single run including iteration list."""

    iterations: list[IterationSummary]
