# Refactoring & Cleanup Roadmap

This document outlines a proposed roadmap for cleaning up and refactoring the codebase before moving on to the next feature. Consider tackling these items incrementally, pairing each with small unit tests to ensure stability.

| Area | Action Items | Files / References |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | |
| **Enforce style & typing** | Apply `ruff` (including import sorting), add `mypy` checks, and introduce `TypedDict` definitions for UI messages for safer refactoring. | `pyproject.toml`, `.pre-commit-config.yaml` |
| **Update docs/architecture** | Reflect the new asynccontextmanager + AsyncExitStack flow and modular slash-command design in the documentation. | `docs/cli.md` |
| **CI / pre-commit** | Add CI workflows (GitHub Actions) to run linters, type checks, and tests on push; configure pre-commit hooks for consistent style. | `.github/workflows/`, `.pre-commit-config.yaml` |

---

**How to use this roadmap:**

1. **Pick one area** and extract/refactor it into its own module or helper.
2. **Write a minimal unit test** to lock in the behavior before deleting the old code.
3. **Merge** and repeat the cycle for the next area until the codebase converges on a clean architecture.

Happy refactoring! 🚀
