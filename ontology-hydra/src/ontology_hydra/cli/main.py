from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

import tiktoken
from chonkie.chunker.token import TokenChunker
from loguru import logger
from tqdm import tqdm

from ontology_hydra.cli.logging import configure_logging
from ontology_hydra.ontology.components.implementation.pipeline import implement_plan
from ontology_hydra.ontology.components.planning.pipeline import generate_plan
from ontology_hydra.ontology.models import BASE_ONTOLOGY
from ontology_hydra.ontology.run import VALID_RUN_NAME_PATTERN, RunMetadata
from ontology_hydra.utils.cache import DirectoryCache

# Initialize logging
configure_logging()

if TYPE_CHECKING:
    from chonkie.types import Chunk


@dataclass(frozen=True, slots=True)
class Args:
    intent: str
    output_dir_path: Path
    name: str
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

    default_name = "run_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    parser.add_argument("--name", type=str, default=default_name, help="Run name (default:)")

    raw = parser.parse_args()
    args = Args(
        intent=raw.intent,
        output_dir_path=Path(raw.output_dir),
        name=raw.name,
        input_paths=[Path(p) for p in raw.input],
    )

    # ---- validate args ---------------------
    if not VALID_RUN_NAME_PATTERN.match(args.name):
        parser.error("Invalid run name!")

    if (args.output_dir_path / args.name).exists():
        parser.error(f"A run with name {args.output_dir_path / args.name} already exists!")

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

    run_dir = args.output_dir_path / args.name
    run_dir.mkdir()

    cache = DirectoryCache(run_dir)
    logger.info("Cache path: {}", cache.path)

    meta = RunMetadata(
        name=args.name,
        intent=args.intent,
        input_files=[p.name for p in args.input_paths],
        created_at=datetime.now(),
        n_iterations=0,
    )

    cache.write("run.json", meta.model_dump_json(indent=4))

    # --- read and chunk inputs -----------------

    texts = [
        tp.read_text(encoding="utf-8", errors="ignore") for tp in args.input_paths
    ]  # TODO: add support for other text formats

    encoding = tiktoken.get_encoding("o200k_base")
    chunker = TokenChunker(chunk_size=1024, chunk_overlap=256, tokenizer=encoding)  # pyright: ignore[reportArgumentType] # tiktoken encoding as argument does work

    chunks_by_text = cast(
        "list[list[Chunk]]", chunker(texts, show_progress_bar=False)
    )  # returns a list of chunks per input text

    ontology = BASE_ONTOLOGY

    for i in tqdm(range(50)):
        logger.info("Iteration {}/50", i + 1)

        plan = generate_plan(args.intent, ontology)
        cache.write((i, "plan.md"), plan)

        ops, review, ontology = implement_plan(plan, args.intent, ontology, max_attempts=10)
        cache.write((i, "ops.json"), ops.model_dump_json(indent=4))
        cache.write(
            (i, "review.md"),
            f"{review.text}\n\n---\n\nVerdict: **{'ACCEPT' if review.accepted else 'REJECT'}**",
        )
        cache.write((i, "ontology.json"), ontology.model_dump_json(indent=2))

        logger.info(
            "Iteration {} complete: {} classes, {} properties",
            i + 1,
            len(ontology.classes),
            len(ontology.data_properties) + len(ontology.object_properties),
        )
        meta.n_iterations = i + 1
        cache.write("run.json", meta.model_dump_json(indent=4))

    exit(0)

    for chunks, text in zip(chunks_by_text, texts, strict=True):
        print(len(chunks), "chunks for", len(text), "chars of text")
        for chunk in chunks:
            pass
