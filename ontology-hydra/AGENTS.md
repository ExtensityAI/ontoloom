# Repository Guidelines

## Project Structure & Module Organization
- Source code lives in `src/ontology_hydra/`, with domain logic under `ontology/`, KG tooling under
  `kg/`, and shared utilities under `utils/`.
- Prompts and higher-level orchestration live in `src/ontology_hydra/prompts.py`.
- `demo.py` is the CLI-style demo entry point; treat it as the canonical example of how to wire the
  pipeline together.

## Build, Test, and Development Commands
- Install dependencies with your preferred tool from `pyproject.toml` (Python >= 3.12).
- Build a package artifact with `uv build` to exercise the build backend (`uv_build`).
- Run the demo pipeline with:
  `uv run python demo.py "intent text" -i path/to/input.txt -o path/to/output/`
- Lint with `ruff check src demo.py --config ruff.toml` to keep style and quality consistent.

## Coding Style & Naming Conventions
- Python style: 4-space indentation, 100-char line length, double quotes (see `ruff.toml`).
- Module and function names are `snake_case`; classes use `PascalCase`.
- Keep imports grouped: standard library, third-party, then local.

## Testing Guidelines
- There is no `tests/` directory or test runner wired up yet.
- If you add tests, place them under `tests/` and follow `test_*.py` naming.
- Document any new test command you introduce (e.g., `pytest -q`) in this file.

## Commit & Pull Request Guidelines
- Commit messages follow Conventional Commits (examples from history: `feat(ontology): ...`,
  `chore: ...`).
- PRs should describe the change, reference related issues, and call out behavior or schema impacts.

## Configuration & Dependencies
- Dependencies and metadata are defined in `pyproject.toml`; linting config is in `ruff.toml`.
- Keep new dependencies minimal and update `pyproject.toml` when you add any.
