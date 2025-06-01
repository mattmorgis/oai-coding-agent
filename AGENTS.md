# AGENTS.md

This file provides guidance coding agents when working with code in this repository.

## Project Overview

This is an interactive coding agent built with the OpenAI Agents SDK and Model Context Protocol (MCP) for exploring and interacting with a local codebase. The agent is implemented as an interactive command line interface (CLI).

### Package Management

This project uses `uv` for project management.

`uv add`: Add a dependency to the project.
`uv add <dep> --dev`: Add a development dependency
`uv remove`: Remove a dependency from the project.
`uv sync`: Sync the project's dependencies with the environment.
`uv lock`: Create a lockfile for the project's dependencies.
`uv run`: Run a command in the project environment.
Example: `uv run script.py`
`uv tree`: View the dependency tree for the project.

### Running Linting

```bash
uv run ruff check
uv run ruff check --fix # optional to auto-fix
```

### Run Formatting

```bash
uv run ruff format # auto formats files by default
uv run ruff format --check # dry run
```

### Running Type Checks

```
uv run mypy .
```

### Running Tests

```bash
uv run pytest
```

### Test Fixtures

All test fixtures should be in the `tests/conftest.py` file.
Please reference `tests/conftest.py` before creating new fixtures.

Only create new fixtures in test files if they are specific to that test file's use cases.
Otherwise, add them to conftest.py for reuse across test files.

### Build and Test Requirements

1. After ALL code changes:

   - Run checks & tests for the specific module you modified:
     ```
     uv run ruff check
     uv run ruff format
     uv run mypy .
     uv run pytest
     ```
   - Fix any test errors (warnings can be ignored)
   - If tests pass, proceed with commit
   - If tests fail, fix issues and rerun tests

2. Documentation:

   - Update relevant documentation if API changes
   - Add docstrings for new functions/classes
   - Update domain model if entity relationships change

3. Code Style:

   - Follow .editorconfig rules
   - Use type hints for all new code
   - Add comments for complex logic
   - Keep functions focused and small
