from argparse import ArgumentParser
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, cast

import tiktoken
from chonkie.chunker.token import TokenChunker

if TYPE_CHECKING:
    from chonkie.types import Chunk

logger = getLogger(__name__)

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


args = parser.parse_args()

intent: str = args.intent
output_path: Path = args.output
input_paths: list[Path] = args.input

# ---- validate args ---------------------
for path in input_paths:
    if not path.exists():
        msg = f"Input path '{path}' does not exist!"
        raise ValueError(msg)

    if path.is_dir():
        msg = f"Input path '{path}' points to a directory but must point to a file!"
        raise ValueError(msg)

if not output_path.is_dir():
    msg = f"Output path '{output_path}' either does not exist or is not a directory"
    raise ValueError(msg)


print(f"{input_paths=}")

# --- read and chunk inputs -----------------

texts = [
    tp.read_text(encoding="utf-8", errors="ignore") for tp in input_paths
]  # TODO: add support for other text formats

encoding = tiktoken.get_encoding("o200k_base")
chunker = TokenChunker(chunk_size=1024, chunk_overlap=256, tokenizer=encoding)  # pyright: ignore[reportArgumentType] # tiktoken encoding as argument does work


chunks_by_text = cast(
    "list[list[Chunk]]", chunker(texts)
)  # returns a list of chunks per input text

for chunks, text in zip(chunks_by_text, texts, strict=True):
    print(len(chunks), "chunks for", len(text), "chars of text")
