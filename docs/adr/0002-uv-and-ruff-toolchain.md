# ADR 0002: uv + ruff toolchain (drop Poetry, black, isort)

- Status: accepted
- Date: 2026-07-06

## Context

v1 used Poetry (with the Python version pinned to exactly 3.12.4), black, isort, and ruff side by side, plus a poetry-auto-export plugin to keep `requirements.txt` in sync.

## Decision

- **uv** for dependency management, lockfile (`uv.lock`), and virtualenvs.
- **ruff** for both linting and formatting (replaces black + isort + flake8-style checks).
- **mypy** in strict mode for type checking.
- **pytest** for tests.
- Python **3.13**, required as `>=3.13` (no exact pin).

## Alternatives considered

- **Keep Poetry**: still maintained, but uv is the de-facto 2026 standard, dramatically faster, and removes the need for the export plugin (Docker installs from `uv.lock` directly).

## Consequences

- `requirements.txt`, Poetry sections in `pyproject.toml`, and the auto-export plugin are removed.
- CI and Docker use `uv sync --frozen` against `uv.lock`.
- Contributors need uv installed (documented in README).
