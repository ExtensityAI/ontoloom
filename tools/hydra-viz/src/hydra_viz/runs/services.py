import json
from pathlib import Path

from ontology_hydra.metrics.structural import (
    StructuralMetrics,
    compute_structural_metrics,
)
from ontology_hydra.ontology.models import Ontology
from ontology_hydra.ontology.revision.operations import Operation
from ontology_hydra.ontology.run import VALID_RUN_ID_PATTERN, RunMetadata
from pydantic import TypeAdapter

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


def _validate_run_id(id: str) -> None:
    if not id or not VALID_RUN_ID_PATTERN.match(id):
        raise ValueError("Invalid run id")


def get_runs_in_dir(dir_path: Path) -> list[Run]:
    """Get all runs in a directory."""
    if not dir_path.is_dir():
        raise ValueError("Must be a directory path")

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


def get_run_by_id(dir_path: Path, id: str):
    """Load a single run by id"""
    _validate_run_id(id)

    run_path = dir_path / id

    # Check directory exists before resolving (avoid info leak)
    if not run_path.exists():
        return None

    # ensure run is a child of our fixed path
    _validate_is_child(dir_path, run_path)

    run_json_path = run_path / "run.json"

    if not run_json_path.is_file():
        # weird, someone messed with this
        return None

    metadata = RunMetadata.model_validate_json(run_json_path.read_text())

    return Run(dir=run_path, metadata=metadata)


def _cache_path(run: Run, iteration: int, filename: str) -> Path:
    """Build path to a cache file for a specific iteration."""
    return run.dir / str(iteration) / filename


def _load_ontology(run: Run, iteration: int) -> Ontology | None:
    """Load ontology JSON for an iteration."""
    path = _cache_path(run, iteration, ONTOLOGY_FILE)
    if not path.is_file():
        return None
    try:
        return Ontology.model_validate_json(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _load_metrics(run: Run, iteration: int) -> StructuralMetrics | None:
    """Load ontology and compute metrics for an iteration."""
    ontology = _load_ontology(run, iteration)
    if ontology is None:
        return None
    return compute_structural_metrics(ontology)


def _load_ops(run: Run, iteration: int) -> list[Operation]:
    """Load operations for an iteration."""
    path = _cache_path(run, iteration, OPS_FILE)
    if not path.is_file():
        return []

    try:
        adapter = TypeAdapter(list[Operation])
        parsed = json.loads(path.read_text())

        # Handle both formats: {"operations": [...]} or [...]
        if isinstance(parsed, dict) and "operations" in parsed:
            return adapter.validate_python(parsed["operations"])
        return adapter.validate_python(parsed)
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
    cache_dir = run.dir / "cache" / str(idx)

    has_ontology = (cache_dir / ONTOLOGY_FILE).is_file()
    has_ops = (cache_dir / OPS_FILE).is_file()
    has_plan = (cache_dir / PLAN_FILE).is_file()
    has_review = (cache_dir / REVIEW_FILE).is_file()

    return IterationSummary(
        index=idx,
        has_ontology=has_ontology,
        has_ops=has_ops,
        has_plan=has_plan,
        has_review=has_review,
        metrics=_load_metrics(run, idx) if has_ontology else None,
    )


def get_run_detail(dir_path: Path, id: str) -> RunDetail | None:
    """Load run with iteration summaries."""
    run = get_run_by_id(dir_path, id)

    if run is None:
        return None

    # Build iteration summaries
    iterations = [
        _build_iteration_summary(run, idx) for idx in range(run.metadata.n_iterations)
    ]

    return RunDetail(dir=run.dir, metadata=run.metadata, iterations=iterations)


def get_iteration_detail(dir_path: Path, id: str, idx: int) -> IterationDetail | None:
    """Load full iteration data."""
    run = get_run_by_id(dir_path, id)
    if run is None:
        return None

    ontology = _load_ontology(run, idx)

    return IterationDetail(
        index=idx,
        ontology=ontology,
        ops=_load_ops(run, idx),
        plan=_load_text_file(run, idx, PLAN_FILE),
        review=_load_text_file(run, idx, REVIEW_FILE),
        metrics=compute_structural_metrics(ontology) if ontology else None,
    )


def get_metrics_time_series(dir_path: Path, id: str) -> MetricsTimeSeries | None:
    """Load metrics for all iterations."""
    run = get_run_by_id(dir_path, id)
    if run is None:
        return None

    points = [
        MetricsTimeSeriesPoint(iteration=idx, metrics=m)
        for idx in range(run.metadata.n_iterations)
        if (m := _load_metrics(run, idx)) is not None
    ]

    return MetricsTimeSeries(name=id, points=points)
