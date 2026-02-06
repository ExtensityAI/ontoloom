from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from loguru import logger
from tqdm import tqdm

from ontology_hydra.cli.components.title import generate_title
from ontology_hydra.cli.logging import configure_logging
from ontology_hydra.metrics import compute_iteration_metrics, compute_ontology_metrics
from ontology_hydra.ontology.components.implementation.pipeline import implement_plan
from ontology_hydra.ontology.components.planning.pipeline import generate_plan
from ontology_hydra.ontology.models import BASE_ONTOLOGY
from ontology_hydra.ontology.run import VALID_RUN_ID_PATTERN, RunMetadata
from ontology_hydra.utils.cache import DirectoryCache

# Initialize logging
configure_logging()


@dataclass(frozen=True, slots=True)
class Args:
    intent: str
    output_dir_path: Path
    id: str
    input_paths: list[Path]


def _parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        "intent",
        type=str,
        help="User intent",
    )

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        nargs="+",
        required=True,
        help="Path to input files",
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="Path to output directory",
    )

    default_id = "run_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    parser.add_argument(
        "--id", type=str, default=default_id, help=f"Run id (default: {default_id})"
    )

    raw = parser.parse_args()
    args = Args(
        intent=raw.intent,
        output_dir_path=Path(raw.output_dir),
        id=raw.id,
        input_paths=[Path(p) for p in raw.input],
    )

    # ---- validate args ---------------------
    if not VALID_RUN_ID_PATTERN.match(args.id):
        parser.error("Invalid run name!")

    if (args.output_dir_path / args.id).exists():
        parser.error(f"A run with id {args.output_dir_path / args.id} already exists!")

    for path in args.input_paths:
        if not path.exists():
            parser.error(f"Input path '{path}' does not exist!")

        if path.is_dir():
            parser.error(f"Input path '{path}' points to a directory but must point to a file!")

    if not args.output_dir_path.is_dir():
        parser.error(
            f"Output path '{args.output_dir_path}' either does not exist or is not a directory"
        )

    return args


def main():
    args = _parse_args()
    logger.info("Input files: {}", [str(p) for p in args.input_paths])

    run_dir = args.output_dir_path / args.id
    run_dir.mkdir()

    cache = DirectoryCache(run_dir)
    logger.info("Cache path: {}", cache.path)

    title = generate_title(args.intent)

    meta = RunMetadata(
        id=args.id,
        title=title,
        intent=args.intent,
        input_files=[p.name for p in args.input_paths],
        created_at=datetime.now(),
        n_iterations=0,
    )

    cache.write("run.json", meta.model_dump_json(indent=4))

    ontology = BASE_ONTOLOGY

    for i in tqdm(range(50)):
        logger.info("Iteration {}/50", i + 1)

        old_ontology = ontology.clone()
        plan = generate_plan(args.intent, ontology)
        cache.write((i, "plan.md"), plan)

        ops, review, ontology = implement_plan(plan, args.intent, ontology, max_attempts=10)
        cache.write((i, "ops.json"), ops.model_dump_json(indent=4))
        cache.write(
            (i, "review.md"),
            f"{review.text}\n\n---\n\nVerdict: **{'ACCEPT' if review.accepted else 'REJECT'}**",
        )
        cache.write((i, "ontology.json"), ontology.model_dump_json(indent=2))
        ontology_metrics = compute_ontology_metrics(ontology)
        iteration_metrics = compute_iteration_metrics(ops.ops, old_ontology, ontology)
        cache.write(
            (i, "ontology_metrics.json"),
            ontology_metrics.model_dump_json(indent=2),
        )
        cache.write(
            (i, "iteration_metrics.json"),
            iteration_metrics.model_dump_json(indent=2),
        )

        logger.info(
            "Iteration {} complete: {} classes, {} properties",
            i + 1,
            len(ontology.classes),
            len(ontology.data_properties) + len(ontology.object_properties),
        )
        meta.n_iterations = i + 1
        cache.write("run.json", meta.model_dump_json(indent=4))
