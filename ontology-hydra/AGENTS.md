# Repository Guidelines

## Coding Style & Naming Conventions

- Python style: 4-space indentation, 100-char line length, double quotes (see `ruff.toml`).
- Module and function names are `snake_case`; classes use `PascalCase`.
- Keep imports grouped: standard library, third-party, then local.
- Do not add return type hints if they can be inferred from the code (Pylance handles inference).
- when writing exceptions, always assign the message to a variable `msg` first and then instantiate the exception from that
- instead of writing `x: set[str] = set()` always write `x = set[str]()` (same for `list` and `dict`)

## Commit & Pull Request Guidelines

- Commit messages follow Conventional Commits (examples from history: `feat(ontology): ...`,
  `chore: ...`).
- PRs should describe the change, reference related issues, and call out behavior or schema impacts.

## Configuration & Dependencies

- Dependencies and metadata are defined in `pyproject.toml`; linting config is in `ruff.toml`.
- Keep new dependencies minimal and update `pyproject.toml` when you add any.
