"""CLI entry point for hydra-viz server."""

import argparse
from pathlib import Path

import uvicorn

from hydra_viz.app import create_app


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="hydra-viz",
        description="Web visualization server for ontology-hydra runs",
    )
    parser.add_argument(
        "runs_dir",
        type=Path,
        help="Path to the runs directory (e.g., .hydra/cache)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8080,
        help="Port to listen on",
    )
    parser.add_argument(
        "-H",
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to",
    )

    args = parser.parse_args()

    # Validate runs directory
    if not args.runs_dir.exists():
        parser.error(f"Runs directory does not exist: {args.runs_dir}")

    if not args.runs_dir.is_dir():
        parser.error(f"Path is not a directory: {args.runs_dir}")

    return args


def main():
    """Main entry point for the hydra-viz CLI."""
    args = _parse_args()

    app = create_app(args.runs_dir.resolve())

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
