from argparse import ArgumentParser
from logging import getLogger
from pathlib import Path

import tiktoken
from chonkie.chunker.token import TokenChunker

from ontology_hydra import generate_kg, ontopipe
from ontology_hydra.utils.cache import DirectoryCache

logger = getLogger(__name__)

parser = ArgumentParser(
    description="Run the ontopipe pipeline to generate an ontology and knowledge graph."
)
parser.add_argument(
    "--domain",
    type=str,
    required=True,
    help="The domain for which to generate the ontology.",
)
parser.add_argument(
    "-o",
    "--output",
    type=Path,
    required=True,
    help="Output directory for the generated ontology and knowledge graph.",
)
parser.add_argument(
    "-i",
    "--input",
    type=Path,
    nargs="+",
    required=True,
    help="Paths to text files to process for knowledge graph generation.",
)

args = parser.parse_args()

domain = args.domain
output_path = args.output
text_paths = args.input


if not output_path.exists():
    msg = f"Output path '{output_path}' does not exist or is not a directory."
    raise ValueError(msg)

cache = DirectoryCache(output_path)

ontology = ontopipe(domain, cache=cache, cqs_per_batch=25)  # saves to cache_path / 'ontology.json'
# use 25 CQs per batch because we use GPT-5.1 and it produced so much data, else it would take way too long

texts = [
    tp.read_text(encoding="utf-8", errors="ignore") for tp in text_paths
]  # TODO add support for other text formats

tokenizer = tiktoken.get_encoding("o200k_base")
chunker = TokenChunker(chunk_size=1024, chunk_overlap=256, tokenizer=tokenizer)

chunks = chunker(texts)

texts = [c.text for cg in chunks for c in cg]


logger.info("Generated %i text chunks for knowledge graph generation.", len(texts))

kg = generate_kg(
    texts=texts,
    ontology=ontology,
    cache=cache,
    epochs=5,  # iterates multiple times over the texts to improve the KG
)
