from argparse import ArgumentParser
from dataclasses import dataclass
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
from ontology_hydra.utils.cache import DirectoryCache

# Initialize logging
configure_logging()

if TYPE_CHECKING:
    from chonkie.types import Chunk


@dataclass(frozen=True, slots=True)
class Args:
    intent: str
    output_path: Path
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
        "--output",
        type=Path,
        required=True,
        help="Path to output directory",
    )

    raw = parser.parse_args()
    args = Args(
        intent=raw.intent, output_path=Path(raw.output), input_paths=[Path(p) for p in raw.input]
    )

    # ---- validate args ---------------------
    for path in args.input_paths:
        if not path.exists():
            msg = f"Input path '{path}' does not exist!"
            raise ValueError(msg)

        if path.is_dir():
            msg = f"Input path '{path}' points to a directory but must point to a file!"
            raise ValueError(msg)

    if not args.output_path.is_dir():
        msg = f"Output path '{args.output_path}' either does not exist or is not a directory"
        raise ValueError(msg)

    return args


def main():
    args = _parse_args()
    logger.info("Input files: {}", [str(p) for p in args.input_paths])

    # --- read and chunk inputs -----------------

    texts = [
        tp.read_text(encoding="utf-8", errors="ignore") for tp in args.input_paths
    ]  # TODO: add support for other text formats

    encoding = tiktoken.get_encoding("o200k_base")
    chunker = TokenChunker(chunk_size=1024, chunk_overlap=256, tokenizer=encoding)  # pyright: ignore[reportArgumentType] # tiktoken encoding as argument does work

    chunks_by_text = cast(
        "list[list[Chunk]]", chunker(texts, show_progress_bar=False)
    )  # returns a list of chunks per input text

    cache = DirectoryCache(args.output_path / "cache")
    logger.info("Cache path: {}", cache.path)

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

    exit(0)

    for chunks, text in zip(chunks_by_text, texts, strict=True):
        print(len(chunks), "chunks for", len(text), "chars of text")
        for chunk in chunks:
            pass
