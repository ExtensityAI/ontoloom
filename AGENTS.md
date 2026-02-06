# Language-specific Guidelines

## Python

- Python style: 4-space indentation, 100-char line length, double quotes (see `ruff.toml` in the root of your Python project).
  - format code using `ruff format [FILES]...`
  - check for errors using `ruff check [FILES]...`
  - if fixable errors occur, use the `--fix` option as written
- Do not add return type hints if they can be inferred from the code (Pylance handles inference).
- when writing exceptions, always assign the message to a variable `msg` first and then instantiate the exception from that
- instead of writing `x: set[str] = set()` always write `x = set[str]()` (same for `list` and `dict`)
- style your code according to best practices for the minimal Python version defined in `pyproject.toml`
- Never use `from __future__ import annotations`; rely on Ruff fixes instead.
- If Ruff reports fixable issues, run `ruff check --fix` rather than manual workarounds.
- Dependencies and metadata are defined in `pyproject.toml`; linting config is in `ruff.toml`.
- Keep new dependencies minimal. Use `uv add` to add new dependencies if necessary.

## Frontend (Svelte/TypeScript)

- Project location: `tools/hydra-viz/frontend`.
- Formatting uses Prettier. Run `pnpm format` (or `prettier --write .`).
- Linting uses Prettier + ESLint. Run `pnpm lint` (runs `prettier --check .` and `eslint .`).
- Type-checking uses `svelte-check`: run `pnpm check`.
- Prettier config: 2-space indentation, double quotes, no semicolons, no trailing commas, print width 100.
- Prettier plugins: `prettier-plugin-svelte` and `prettier-plugin-tailwindcss` (Tailwind stylesheet at `tools/hydra-viz/frontend/src/layout.css`).

# General Guidelines

- Commit messages follow Conventional Commits (examples from history: `feat(ontology): ...`,
  `chore: ...`).
- PRs should describe the change, reference related issues, and call out behavior or schema impacts.

## Memories

- When you learn stable takeaways or I say something was a mistake, update the relevant subproject's `AGENTS.md` (add/adjust/remove) so future work is faster.
  - e.g. in `ontology-hydra`, `tools/hydra-viz` (Python) and `tools/hydra-viz/frontend` (Svelte)
  - if the `AGENTS.md` of the subproject does not exist then, create it
