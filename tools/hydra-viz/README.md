# hydra-viz

Web-based visualization and analysis server for [ontology-hydra](../../) runs. Explore ontology evolution across iterations with interactive graphs, metrics charts, and change tracking.

## Features

- **Run Browser** -- List and navigate all ontology generation runs
- **Metrics Dashboard** -- Track class count, hierarchy depth, property coverage, and branching factor over iterations
- **Interactive Graph** -- Explore class hierarchies and relationships with a force-directed WebGL visualization (Sigma.js)
- **Change Inspector** -- View the plan, operations, and review verdict for each iteration

## Setup

Requires Python 3.14+ and [uv](https://github.com/astral-sh/uv).

```bash
uv sync
```

## Usage

Point the server at a directory containing HyDRA run outputs:

```bash
uv run hydra-viz /path/to/runs/
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `-p, --port` | `8080` | Port to listen on |
| `-H, --host` | `127.0.0.1` | Host to bind to |
| `--api` | -- | API-only mode (no UI) |

The server provides a REST API at `/api/runs` and OpenAPI docs at `/docs`.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/runs` | List all runs |
| `GET` | `/api/runs/{id}` | Get run with all iterations |
| `GET` | `/api/runs/{id}/iterations/{idx}` | Get a specific iteration |
| `GET` | `/api/runs/{id}/metrics` | Get time-series metrics |

## Building from Source

The Makefile builds the frontend and bundles it into the Python package:

```bash
make all    # clean + build frontend + build Python wheel
make frontend   # build frontend only
make python     # build Python package (requires frontend)
make clean      # remove build artifacts
```

Requires [pnpm](https://pnpm.io/) for the frontend build step.

## Architecture

```
hydra-viz/
  src/hydra_viz/       Python backend (Litestar + Uvicorn)
  frontend/            Svelte frontend (SvelteKit + Vite)
```

The backend serves the built frontend as static assets and exposes the REST API. See the [frontend README](frontend/) for frontend development details.
