from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ontology_hydra.ontology.run import VALID_RUN_ID_PATTERN


@dataclass(frozen=True, slots=True)
class InitArgs:
    config_path: Path


@dataclass(frozen=True, slots=True)
class GenerateOntologyArgs:
    intent: str
    output_dir_path: Path
    id: str
    input_paths: list[Path]
    config_path: Path


def parse_args(argv: list[str]):
    parser = ArgumentParser(prog="hydra")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="Path to config file to create",
    )

    generate_ontology_parser = subparsers.add_parser("generate-ontology")
    generate_ontology_parser.add_argument(
        "intent",
        type=str,
        help="User intent",
    )

    generate_ontology_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="Path to config file",
    )

    generate_ontology_parser.add_argument(
        "-i",
        "--input",
        type=Path,
        nargs="+",
        required=True,
        help="Path to input files",
    )

    generate_ontology_parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="Path to output directory",
    )

    default_id = "run_" + datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")

    generate_ontology_parser.add_argument(
        "--id",
        type=str,
        default=default_id,
        help=f"Run id (default: {default_id})",
    )

    raw = parser.parse_args(argv)

    if raw.command == "init":
        # init only takes one arg
        return "init", InitArgs(config_path=raw.config)

    if not raw.config.exists():
        generate_ontology_parser.error(
            f"Config file '{raw.config}' not found. Run `hydra init --config '{raw.config}'`.",
        )
    if raw.config.is_dir():
        generate_ontology_parser.error(
            f"Config path '{raw.config}' points to a directory, not a file.",
        )

    args = GenerateOntologyArgs(
        intent=raw.intent,
        output_dir_path=raw.output_dir,
        id=raw.id,
        input_paths=raw.input,
        config_path=raw.config,
    )

    if not VALID_RUN_ID_PATTERN.match(args.id):
        generate_ontology_parser.error("Invalid run name!")

    if (args.output_dir_path / args.id).exists():
        generate_ontology_parser.error(
            f"A run with id {args.output_dir_path / args.id} already exists!",
        )

    for path in args.input_paths:
        if not path.exists():
            generate_ontology_parser.error(f"Input path '{path}' does not exist!")

        if path.is_dir():
            generate_ontology_parser.error(
                f"Input path '{path}' points to a directory but must point to a file!",
            )

    if not args.output_dir_path.is_dir():
        generate_ontology_parser.error(
            f"Output path '{args.output_dir_path}' either does not exist or is not a directory",
        )

    return "generate-ontology", args
