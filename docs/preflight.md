# Preflight Checks

The `oai` CLI now performs a set of *preflight checks* before running commands to ensure the environment meets the requirements. These checks are always run and **cannot be skipped**.

## What is checked

- **Git worktree**: Verifies that the current Git worktree is clean and on a supported branch.
- **Node.js**: Ensures Node.js is installed and meets the minimum required version.
- **Docker**: Checks that Docker is installed, reachable, and running.

## Failure behavior

If any preflight check fails, the CLI:

1. Prints error messages describing the failures.
2. Exits immediately with a non-zero status code.

## Logging

The tool versions and check results are logged to:

```
~/.oai_coding_agent/agent.log
```

## No skip flags

There are no flags or options to skip the preflight checks. This ensures that the agent always runs in a validated environment.

## Adding future checks

To extend the preflight process:

1. Add the new check in the preflight implementation (e.g., `oai_coding_agent.preflight`).
2. Document the new check in `docs/preflight.md`.
3. Update the CLI flowchart in `docs/cli.md` to reflect the added step.
