"""API route handlers for hydra-viz."""

from typing import TypeVar

from litestar import Router, get
from litestar.exceptions import NotFoundException

from hydra_viz.context import Context

from .models import IterationDetail, MetricsTimeSeries, Run, RunDetail
from .services import (
    get_iteration_detail,
    get_metrics_time_series,
    get_run_detail,
    get_runs_in_dir,
)

T = TypeVar("T")


@get("", name="get-runs")
async def list_runs(ctx: Context) -> list[Run]:
    """List all available runs."""
    return get_runs_in_dir(ctx.path)


@get("/{name:str}", name="get-run")
async def get_run(ctx: Context, name: str) -> RunDetail:
    """Get run detail with iterations."""
    run = get_run_detail(ctx.path, name)

    if run is None:
        raise NotFoundException(f"Run '{name}' not found!")

    return run


@get("/{name:str}/iterations/{idx:int}", name="get-iteration")
async def get_iteration(ctx: Context, name: str, idx: int) -> IterationDetail:
    """Get iteration detail."""
    detail = get_iteration_detail(ctx.path, name, idx)

    if detail is None:
        raise NotFoundException(f"Iteration detail '{name}'.{idx} not found")

    return detail


@get("/{name:str}/metrics", name="get-metrics")
async def get_metrics(ctx: Context, name: str) -> MetricsTimeSeries:
    """Get metrics time series for a run."""
    metrics = get_metrics_time_series(ctx.path, name)

    if metrics is None:
        raise NotFoundException(f"Metrics not found for run '{name}'")

    return metrics


runs_router = Router(
    path="/api/runs",
    route_handlers=[list_runs, get_run, get_iteration, get_metrics],
)
