import logging
from pathlib import Path

from litestar import Litestar
from litestar.di import Provide
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import ScalarRenderPlugin
from litestar.static_files import create_static_files_router

from ontoloom_viz.context import Context
from ontoloom_viz.runs.routes import runs_router

logger = logging.getLogger(__name__)


def create_app(path: Path):
    context = Context(path=path)

    route_handlers = [runs_router]

    # Determine static files directory (relative to this module)
    static_dir = Path(__file__).parent / "static"

    if not static_dir.exists():
        msg = f"Could not start: static directory to serve UI was not found under {static_dir}"
        raise FileNotFoundError(msg)

    static_router = create_static_files_router(
        path="/",
        directories=[static_dir],
        html_mode=True,  # Serve index.html for SPA routing
    )

    route_handlers.append(static_router)

    return Litestar(
        route_handlers=route_handlers,
        dependencies={"ctx": Provide(lambda: context, sync_to_thread=False)},
        openapi_config=OpenAPIConfig(
            title="ontology-hydra Visualizer Backend API",
            version="0.0.1",
            render_plugins=[ScalarRenderPlugin()],
            path="/docs",
        ),
    )
