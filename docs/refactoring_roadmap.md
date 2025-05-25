# Refactoring & Cleanup Roadmap

This document outlines a proposed roadmap for cleaning up and refactoring the codebase before moving on to the next feature. Consider tackling these items incrementally, pairing each with small unit tests to ensure stability.

| Area                         | Action Items                                                                                                                      | Files / References                                      |
|------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------|
| **Slash-command registry**   | Extract slash-commands out of `rich_tui.py` into their own module or class, avoiding redefinition on each run.                     | `src/oai_coding_agent/rich_tui.py` (L66–111)            |
| **Eliminate module globals** | Move `messages` and `slash_commands` off the module top level into an instance that holds UI state for cleaner encapsulation.     | `src/oai_coding_agent/rich_tui.py` (L38–41)             |
| **Decouple TUI concerns**    | Split the giant `rich_tui.py` into focused modules: input loop, rendering logic, slash-commands, and key-bindings.               | `src/oai_coding_agent/rich_tui.py`                      |
| **DRY up CLI options**       | Factor out repeated `openai_api_key`, `model`, and `repo_path` Typer options in `cli.py` into shared defaults or a callback.       | `src/oai_coding_agent/cli.py` (L50–100)                 |
| **Centralize env loading**   | Move `.env` loading and `OPENAI_API_KEY` setup into a single initialization function or config utility.                           | `src/oai_coding_agent/cli.py` (L21–25)                  |
| **Add unit tests**           | Write tests for `_map_sdk_event`, `_AgentSession` startup/cleanup, slash-command handlers, and TUI renderers.                      | `tests/` folder                                          |
| **Enforce style & typing**   | Apply `ruff`, `black`, `isort`, add `mypy` checks, and introduce `TypedDict` definitions for UI messages for safer refactoring.   | `pyproject.toml`, `.pre-commit-config.yaml`              |
| **Update docs/architecture** | Reflect the new asynccontextmanager + AsyncExitStack flow and modular slash-command design in the documentation.                   | `docs/cli.md`                                           |
| **CI / pre-commit**          | Add CI workflows (GitHub Actions) to run linters, type checks, and tests on push; configure pre-commit hooks for consistent style. | `.github/workflows/`, `.pre-commit-config.yaml`          |

---

**How to use this roadmap:**

1. **Pick one area** and extract/refactor it into its own module or helper.
2. **Write a minimal unit test** to lock in the behavior before deleting the old code.
3. **Merge** and repeat the cycle for the next area until the codebase converges on a clean architecture.

Happy refactoring! 🚀
