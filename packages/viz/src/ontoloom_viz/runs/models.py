from pathlib import Path

from ontoloom.core.metrics import IterationMetrics, OntologyMetrics
from ontoloom.ontology.models import Ontology
from ontoloom.ontology.revision.operations import Operation
from ontoloom.ontology.run import RunMetadata
from pydantic import BaseModel, Field


class IterationSummary(BaseModel):
    """Summary of a single iteration within a run."""

    index: int
    has_ontology: bool
    has_ops: bool
    has_plan: bool
    has_review: bool
    ontology_metrics: OntologyMetrics | None = None
    iteration_metrics: IterationMetrics | None = None


class IterationDetail(BaseModel):
    """Full data for a single iteration."""

    index: int
    ontology: Ontology | None = None
    ops: list[Operation] = []
    plan: str | None = None
    review: str | None = None
    ontology_metrics: OntologyMetrics | None = None
    iteration_metrics: IterationMetrics | None = None


class MetricsTimeSeriesPoint(BaseModel):
    """A single point in the metrics time series."""

    iteration: int
    ontology_metrics: OntologyMetrics
    iteration_metrics: IterationMetrics | None = None


class MetricsTimeSeries(BaseModel):
    """Metrics over all iterations for a run."""

    name: str
    points: list[MetricsTimeSeriesPoint]


class Run(BaseModel):
    dir: Path = Field(exclude=True)
    metadata: RunMetadata


class RunDetail(Run):
    """Detailed view of a single run including iteration list."""

    iterations: list[IterationSummary]
