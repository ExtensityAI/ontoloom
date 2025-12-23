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

intent = args.intent
output_path = args.output
text_paths = args.input


texts = [
    tp.read_text(encoding="utf-8", errors="ignore") for tp in text_paths
]  # TODO: add support for other text formats

tokenizer = tiktoken.get_encoding("o200k_base")
chunker = TokenChunker(chunk_size=1024, chunk_overlap=256, tokenizer=tokenizer)  # pyright: ignore[reportArgumentType] # tokenizer works

# returns a list of chunks per input text
chunks_by_text = cast("list[list[Chunk]]", chunker(texts))

for chunks, text in zip(chunks_by_text, texts, strict=True):
    print(len(chunks), len(text))
