"""API route handlers for ontoloom-viz."""

from litestar import Router, get
from litestar.exceptions import NotFoundException

from ontoloom_viz.context import Context  # noqa: TC001 # impossible

from .models import IterationDetail, MetricsTimeSeries, Run, RunDetail  # noqa: TC001 # impossible
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


@get("/{run_id:str}", name="get-run")
async def get_run(ctx: Context, run_id: str) -> RunDetail:
    """Get run detail with iterations."""
    run = get_run_detail(ctx.path, run_id)

    if run is None:
        msg = f"Run '{run_id}' not found!"
        raise NotFoundException(msg)

    return run


@get("/{run_id:str}/iterations/{idx:int}", name="get-iteration")
async def get_iteration(ctx: Context, run_id: str, idx: int) -> IterationDetail:
    """Get iteration detail."""
    detail = get_iteration_detail(ctx.path, run_id, idx)

    if detail is None:
        msg = f"Iteration detail '{run_id}'.{idx} not found"
        raise NotFoundException(msg)

    return detail


@get("/{run_id:str}/metrics", name="get-metrics")
async def get_metrics(ctx: Context, run_id: str) -> MetricsTimeSeries:
    """Get metrics time series for a run."""
    metrics = get_metrics_time_series(ctx.path, run_id)

    if metrics is None:
        msg = f"Metrics not found for run '{run_id}'"
        raise NotFoundException(msg)

    return metrics


runs_router = Router(
    path="/api/runs",
    route_handlers=[list_runs, get_run, get_iteration, get_metrics],
)
