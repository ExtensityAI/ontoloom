# **HyDRA: Hybrid-Driven Reasoning Architecture for Ontology Generation**

<img src="https://raw.githubusercontent.com/ExtensityAI/symbolicai/refs/heads/main/assets/images/banner.png">

<div align="center">

[![SymbolicAI](https://img.shields.io/badge/SymbolicAI-blue?style=for-the-badge)](https://github.com/ExtensityAI/symbolicai)
[![Paper](https://img.shields.io/badge/Paper-32758e?style=for-the-badge)](?)
[![DeepWiki](https://img.shields.io/badge/DeepWiki-yellow?style=for-the-badge)](https://deepwiki.com/ExtensityAI/ontology-hydra)

[![Twitter](https://img.shields.io/twitter/url/https/twitter.com/symbolicapi.svg?style=social&label=@ExtensityAI)](https://twitter.com/ExtensityAI)

</div>

---

<div align="center">
  <img src=".assets/ontology.gif" alt="Ontology Visualization" width="800"/>
</div>

## What is HyDRA?

HyDRA generates **domain-specific ontologies** from natural language intent. Give it a domain description and source texts -- it iteratively plans, drafts, validates, and refines a formal OWL 2-compliant ontology over 50 iterations, producing a structured class hierarchy with data and object properties.

Built entirely on [SymbolicAI](https://github.com/ExtensityAI/symbolicai).

### How it works

```
Intent + Source Texts
        |
   [ Planning ]        LLM generates a focused plan for the next aspect
        |
   [ Operations ]      Plan is translated into formal ontology operations
        |
   [ Review ]          LLM validates operations against the plan
        |
   [ Execution ]       Validated operations are applied to the ontology
        |
   [ Iteration ]       Repeat -- ontology grows and refines over 50 cycles
```

Every iteration is cached with its plan, operations, review, and resulting ontology -- giving you a full audit trail.

## Repository Structure

This is a monorepo with the following packages:

| Package | Path | Description |
|---------|------|-------------|
| **ontology-hydra** | [`ontology-hydra/`](ontology-hydra/) | Core ontology generation engine and CLI |
| **hydra-viz** | [`tools/hydra-viz/`](tools/hydra-viz/) | Web-based visualization server for inspecting runs |

## Quick Start

### Prerequisites

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) package manager
- A configured [SymbolicAI](https://extensityai.gitbook.io/symbolicai/installation#configuration-file) engine

### Setup

```bash
git clone git@github.com:ExtensityAI/ontology-hydra.git
cd ontology-hydra/ontology-hydra
uv sync
uv run symconfig  # configure your SymbolicAI engine on first run
```

### Generate an Ontology

```bash
uv run hydra "biography of historical figures" \
  -i data/source.txt \
  -o output/
```

This will create a run directory under `output/` containing all iterations with plans, operations, reviews, and the evolving ontology.

### Visualize Runs

```bash
cd ../tools/hydra-viz
uv sync
uv run hydra-viz output/
```

Opens an interactive dashboard at `http://localhost:8080` for exploring ontology evolution, metrics, and graph structure. See the [hydra-viz README](tools/hydra-viz/) for details.

## API Usage

```python
from ontology_hydra.ontology.models import BASE_ONTOLOGY, Ontology
from ontology_hydra.ontology.components.planning.pipeline import generate_plan
from ontology_hydra.ontology.components.implementation.pipeline import implement_plan

ontology = BASE_ONTOLOGY

for i in range(50):
    plan = generate_plan(intent="your domain description", ontology=ontology)
    ops, review, ontology = implement_plan(plan, intent, ontology, max_attempts=10)

# ontology is now a fully populated Ontology model
```

## License

See [LICENSE](LICENSE) for details.
