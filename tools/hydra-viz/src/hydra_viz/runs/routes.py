"""API route handlers for hydra-viz."""

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


@get("", name="get-runs")
async def list_runs(ctx: Context) -> list[Run]:
    """List all available runs."""
    return get_runs_in_dir(ctx.path)


@get("/{id:str}", name="get-run")
async def get_run(ctx: Context, id: str) -> RunDetail:
    """Get run detail with iterations."""
    run = get_run_detail(ctx.path, id)

    if run is None:
        raise NotFoundException(f"Run '{id}' not found!")

    return run


@get("/{id:str}/iterations/{idx:int}", name="get-iteration")
async def get_iteration(ctx: Context, id: str, idx: int) -> IterationDetail:
    """Get iteration detail."""
    detail = get_iteration_detail(ctx.path, id, idx)

    if detail is None:
        raise NotFoundException(f"Iteration detail '{id}'.{idx} not found")

    return detail


@get("/{id:str}/metrics", name="get-metrics")
async def get_metrics(ctx: Context, id: str) -> MetricsTimeSeries:
    """Get metrics time series for a run."""
    metrics = get_metrics_time_series(ctx.path, id)

    if metrics is None:
        raise NotFoundException(f"Metrics not found for run '{id}'")

    return metrics


runs_router = Router(
    path="/api/runs",
    route_handlers=[list_runs, get_run, get_iteration, get_metrics],
)
