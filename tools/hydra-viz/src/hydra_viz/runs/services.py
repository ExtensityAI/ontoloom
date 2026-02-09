import json
from pathlib import Path

from ontology_hydra.metrics import IterationMetrics, OntologyMetrics
from ontology_hydra.ontology.components.implementation.draft_ops import OperationSequence
from ontology_hydra.ontology.models import Ontology
from ontology_hydra.ontology.revision.operations import Operation
from ontology_hydra.ontology.run import VALID_RUN_ID_PATTERN, RunMetadata

from hydra_viz.runs.models import (
    IterationDetail,
    IterationSummary,
    MetricsTimeSeries,
    MetricsTimeSeriesPoint,
    Run,
    RunDetail,
)

# Cache file names
ONTOLOGY_FILE = "ontology.json"
OPS_FILE = "ops.json"
PLAN_FILE = "plan.md"
REVIEW_FILE = "review.md"
ONTOLOGY_METRICS_FILE = "ontology_metrics.json"
ITERATION_METRICS_FILE = "iteration_metrics.json"


def _validate_run_id(run_id: str) -> None:
    if not run_id or not VALID_RUN_ID_PATTERN.match(run_id):
        msg = "Invalid run id"
        raise ValueError(msg)


def get_runs_in_dir(dir_path: Path) -> list[Run]:
    """Get all runs in a directory."""
    if not dir_path.is_dir():
        msg = "Must be a directory path"
        raise ValueError(msg)

    return [
        Run(dir=p.parent, metadata=RunMetadata.model_validate_json(p.read_text()))
        for p in dir_path.glob("*/run.json")
    ]


def _validate_is_child(parent_path: Path, other_path: Path):
    parent = Path(parent_path).resolve()
    child = Path(other_path).resolve()

    try:
        return child.relative_to(parent) and (child != parent)
    except ValueError:
        return False


def get_run_by_id(dir_path: Path, run_id: str):
    """Load a single run by id"""
    _validate_run_id(run_id)

    run_path = dir_path / run_id

    # Check directory exists before resolving (avoid info leak)
    if not run_path.exists():
        return None

    # ensure run is a child of our fixed path
    if not _validate_is_child(dir_path, run_path):
        return None

    run_json_path = run_path / "run.json"

    if not run_json_path.is_file():
        # weird, someone messed with this
        return None

    metadata = RunMetadata.model_validate_json(run_json_path.read_text())

    return Run(dir=run_path, metadata=metadata)


def _cache_path(run: Run, iteration: int, filename: str) -> Path:
    """Build path to a cache file for a specific iteration."""
    return run.dir / str(iteration) / filename


def _load_json_model(path: Path, model):
    if not path.is_file():
        return None
    try:
        return model.model_validate_json(path.read_text())
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _load_ontology(run: Run, iteration: int) -> Ontology | None:
    """Load ontology JSON for an iteration."""
    path = _cache_path(run, iteration, ONTOLOGY_FILE)
    return _load_json_model(path, Ontology)


def _load_ontology_metrics(run: Run, iteration: int) -> OntologyMetrics | None:
    """Load cached ontology metrics for an iteration."""
    path = _cache_path(run, iteration, ONTOLOGY_METRICS_FILE)
    return _load_json_model(path, OntologyMetrics)


def _load_iteration_metrics(run: Run, iteration: int) -> IterationMetrics | None:
    """Load cached iteration metrics for an iteration."""
    path = _cache_path(run, iteration, ITERATION_METRICS_FILE)
    return _load_json_model(path, IterationMetrics)


def _load_ops(run: Run, iteration: int) -> list[Operation]:
    """Load operations for an iteration."""
    path = _cache_path(run, iteration, OPS_FILE)
    if not path.is_file():
        return []

    try:
        ops = OperationSequence.model_validate_json(path.read_text())
        return ops.ops
    except (json.JSONDecodeError, OSError, ValueError):
        return []


def _load_text_file(run: Run, iteration: int, filename: str) -> str | None:
    """Load a text file (plan.md or review.md) for an iteration."""
    path = _cache_path(run, iteration, filename)
    if not path.is_file():
        return None
    try:
        return path.read_text()
    except OSError:
        return None


def _build_iteration_summary(run: Run, idx: int) -> IterationSummary:
    """Build an iteration summary for a specific iteration index."""
    has_ontology = _cache_path(run, idx, ONTOLOGY_FILE).is_file()
    has_ops = _cache_path(run, idx, OPS_FILE).is_file()
    has_plan = _cache_path(run, idx, PLAN_FILE).is_file()
    has_review = _cache_path(run, idx, REVIEW_FILE).is_file()

    return IterationSummary(
        index=idx,
        has_ontology=has_ontology,
        has_ops=has_ops,
        has_plan=has_plan,
        has_review=has_review,
        ontology_metrics=_load_ontology_metrics(run, idx),
        iteration_metrics=_load_iteration_metrics(run, idx),
    )


def get_run_detail(dir_path: Path, run_id: str) -> RunDetail | None:
    """Load run with iteration summaries."""
    run = get_run_by_id(dir_path, run_id)

    if run is None:
        return None

    # Build iteration summaries
    iterations = [_build_iteration_summary(run, idx) for idx in range(run.metadata.n_iterations)]

    return RunDetail(dir=run.dir, metadata=run.metadata, iterations=iterations)


def get_iteration_detail(dir_path: Path, run_id: str, idx: int) -> IterationDetail | None:
    """Load full iteration data."""
    run = get_run_by_id(dir_path, run_id)
    if run is None:
        return None

    if idx < 0 or idx >= run.metadata.n_iterations:
        return None

    ontology = _load_ontology(run, idx)

    return IterationDetail(
        index=idx,
        ontology=ontology,
        ops=_load_ops(run, idx),
        plan=_load_text_file(run, idx, PLAN_FILE),
        review=_load_text_file(run, idx, REVIEW_FILE),
        ontology_metrics=_load_ontology_metrics(run, idx),
        iteration_metrics=_load_iteration_metrics(run, idx),
    )


def get_metrics_time_series(dir_path: Path, run_id: str) -> MetricsTimeSeries | None:
    """Load metrics for all iterations."""
    run = get_run_by_id(dir_path, run_id)
    if run is None:
        return None

    points = []
    for idx in range(run.metadata.n_iterations):
        ontology_metrics = _load_ontology_metrics(run, idx)
        if ontology_metrics is None:
            continue
        points.append(
            MetricsTimeSeriesPoint(
                iteration=idx,
                ontology_metrics=ontology_metrics,
                iteration_metrics=_load_iteration_metrics(run, idx),
            )
        )

    return MetricsTimeSeries(name=run_id, points=points)
