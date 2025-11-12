# **HyDRA: A Hybrid-Driven Reasoning Architecture for Verifiable Knowledge Graphs**

<img src="https://raw.githubusercontent.com/ExtensityAI/symbolicai/refs/heads/main/assets/images/banner.png">

<div align="center">

[![SymbolicAI](https://img.shields.io/badge/SymbolicAI-blue?style=for-the-badge)](https://github.com/ExtensityAI/symbolicai)
[![Paper](https://img.shields.io/badge/Paper-32758e?style=for-the-badge)](?)
[![DeepWiki](https://img.shields.io/badge/DeepWiki-yellow?style=for-the-badge)](https://deepwiki.com/ExtensityAI/ontology-hydra)

[![Twitter](https://img.shields.io/twitter/url/https/twitter.com/symbolicapi.svg?style=social&label=@ExtensityAI)](https://twitter.com/ExtensityAI)

</div>

---

<div align="center">
  <img src=".assets/ontology.gif" alt="Knowledge Graph Visualization" width="800"/>
</div>

## About

`HyDRA` is a framework for generating **domain-specific ontologies** and **knowledge graphs**. It employs an AI persona committee-based approach to comprehensively scope domains, generate ontological structures, and create knowledge graphs for various applications including question answering and domain exploration. `HyDRA` is built entirely on the [symbolicai](https://github.com/ExtensityAI/symbolicAI) framework. Please support the project by starring the repository.

## Setup

```bash
git clone git@github.com:ExtensityAI/ontology-hydra.git
cd ontology-hydra
```

To set up the environment, install the Python package manager [uv](https://github.com/astral-sh/uv).

Then, create a virtual environment and install the dependencies by running:

```bash
uv sync
```

Now, you need to configure your `symbolicai` config. First, run:

```bash
uv run symconfig
```

Upon running this command for the first time, it will start the initial packages caching and initializing the `symbolicai` configuration files in the `uv`'s `.venv` directory, ultimately displaying the following warning:

```text
UserWarning: No configuration file found for the environment. A new configuration file has been created at <full-path>/ontology-hydra/.venv/.symai/symai.config.json. Please configure your environment.
```

You then must edit the `symai.config.json` file. A neurosymbolic engine is **required** for the `symbolicai` framework to be used. More about configuration management [here](https://extensityai.gitbook.io/symbolicai/installation#configuration-file).

## Usage

### Generating Ontologies and Knowledge Graphs

You can use the `ontology_hydra` API to generate ontologies and knowledge graphs for a specific domain:

```python
from pathlib import Path

from ontology_hydra import generate_kg, ontopipe
from ontology_hydra.ontology.models import Ontology

# Define the domain and output directory
domain = "biography"
cache_path = Path("output/cache")
cache_path.mkdir(parents=True, exist_ok=True)

# Generate ontology
ontology = ontopipe(
    domain=domain,
    cache_path=cache_path,
    group_size=4,  # number of committee members to group for scope/CQ generation
    cqs_per_batch=4  # number of CQs to process per batch during ontology generation
)
# The ontology is automatically saved to cache_path / 'ontology.json'

# Or load from cache
# ontology = Ontology.model_validate_json(
#     (cache_path / 'ontology.json').read_text(encoding='utf-8', errors='ignore')
# )

# Prepare your text data
texts = ['...']  # provide your list of text chunks here
                 # the chunk length has an impact on the quality of the generated KG
                 # shorter chunks = denser KG
                 # longer chunks = sparser KG

# We recommend using the chonkie library for text chunking
# Install the symai plugin: uv run sympkg i ExtensityAI/chonkie-symai
# Example:
import tiktoken
from chonkie import TokenChunker

tokenizer = tiktoken.get_encoding("o200k_base")
chunker = TokenChunker(chunk_size=1024, chunk_overlap=256, tokenizer=tokenizer)

# Assuming you have your text in a list
raw_texts = ["Your text content here..."]
chunks = chunker(raw_texts)
texts = [c.text for cg in chunks for c in cg]

# Generate knowledge graph
kg = generate_kg(
    texts=texts,
    ontology=ontology,
    cache_path=cache_path,
    batch_size=1,  # number of texts to process in parallel
    epochs=3  # iterates multiple times over the texts to improve the KG
)
# The KG is automatically saved to cache_path / 'kg.json'

# Or load from cache
# kg_model = generate_kg_schema(ontology)  # get the dynamic KG schema
# kg = kg_model.model_validate_json(
#     (cache_path / 'kg.json').read_text(encoding='utf-8', errors='ignore')
# )

# Visualize results (requires pyvis)
from ontology_hydra.vis import visualize_knowledge_graph

visualize_knowledge_graph(
    ontology=ontology,
    kg=kg.model_dump(),  # convert to dict
    output_path=cache_path / 'kg_visualization.html'
)
```
