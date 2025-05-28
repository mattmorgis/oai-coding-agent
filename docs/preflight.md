# Preflight Checks

Before executing the CLI in interactive or headless mode, the agent performs a series of preflight checks to ensure the environment is properly configured.

## What is checked

- **Git worktree status**: Verifies that the current Git worktree is clean (no uncommitted changes).
- **Node.js version**: Ensures that Node.js is installed and meets the minimum required version.
- **Docker availability**: Checks that Docker daemon is running and reachable.

## Failure behavior

If any check fails, the CLI will:

1. Print a descriptive error message for each failing check.
2. Exit immediately with a non-zero status code.

## Logging

The preflight checks log their status and version information to:

```
~/.oai_coding_agent/agent.log
```

This helps with debugging and audit trails.

## Skip flags

There are no flags to skip preflight checks. They are always applied to ensure a consistent environment.

## Adding new checks

To add a new preflight check:

1. Update the `preflight` module with your new check implementation.
2. Add an entry in this documentation under **What is checked**.
3. Include any configuration or version requirements in the **Failure behavior** or **Logging** sections as needed.
