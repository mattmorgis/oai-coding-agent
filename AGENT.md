# AGENT.md

This file provides guidance to the OAI coding agent (oai-coding-agent CLI) when working with code in this repository.

## Project Overview

This is an interactive coding agent built with the OpenAI Agents SDK and Model Context Protocol (MCP) for exploring and interacting with a local codebase. The agent is implemented as both a command‑line interface (CLI) and a text‑based user interface (TUI).

## Architecture

The project consists of several key components:

1. **Model Context Protocol (MCP) Server**: Launched via npx to provide access to the local filesystem
2. **Agent Framework**: Using OpenAI's Agents SDK to create and manage the coding assistant
3. **User Interfaces**:
   - Command-line interface (CLI) using typer
   - Text-based UI using the Textual library

The main architecture flow is:
- The MCP server provides filesystem access capabilities
- The agent is initialized with appropriate instructions and model settings
- The user interface (CLI or TUI) manages the interaction loop
- User messages are sent to the agent via the Agent SDK
- Agent responses and tool operations are streamed back to the UI

## Key Files

- `main.py`: Entry point that sets up the MCP server and implements the basic REPL
- `cli.py`: Command-line interface using typer
- `tui.py`: Text-based UI implementation using Textual
- `tui-claude.py`: Alternative TUI implementation focused on Claude
- `prompt.py`: Contains system prompts for the agent

## Development Commands

### Environment Setup

```bash
# Install dependencies
uv sync

# Create and configure environment variables
cp .env-example .env
```

Make sure to set the following in your `.env` file:
- `MOUNT_PATH`: The path to the codebase you want to explore
- `OPENAI_API_KEY`: Your OpenAI API key

### Running the Application

```bash
# Run the main application
uv run main.py

# Run with typer CLI
uv run cli.py

# Run the textual UI
uv run tui.py
# Or the Claude-focused textual UI
uv run tui-claude.py
```

## Library Usage

The codebase depends on:
- `openai-agents[litellm]`: For the agent capabilities
- `python-dotenv`: For environment variable management
- `textual`: For the text-based user interface
- `typer`: For command-line interface

## Development Guidelines

When developing for this codebase:

1. Follow the existing architecture pattern, separating concerns between:
   - Agent configuration
   - UI implementation
   - MCP server integration

2. The project uses `uv` for dependency management instead of pip or other tools.

3. Environment variables are managed through `.env` files with python-dotenv.

## Project Rules

### Package Management

This project uses `uv` for project management.

`uv add`: Add a dependency to the project.
`uv add <dep> --dev`: Add a development dependency
`uv remove`: Remove a dependency from the project.
`uv sync`: Sync the project's dependencies with the environment.
`uv lock`: Create a lockfile for the project's dependencies.
`uv run`: Run a command in the project environment.
Example: `uv run data_acquisition/main.py --email your.email@example.com`
`uv tree`: View the dependency tree for the project.

### Running Tests

# Run tests for a specific module

uv run pytest

### Test Fixtures

All test fixtures should be in the `tests/conftest.py` file.
Please reference `tests/conftest.py` before creating new fixtures.

Only create new fixtures in test files if they are specific to that test file's use cases.
Otherwise, add them to conftest.py for reuse across test files.

### Build and Test Requirements

IMPORTANT:

### DO NOT CREATE **init**.py FILES ANYWHERE IN THIS PROJECT

1. Test-Driven Development (TDD) Workflow:

   - Always check for and update corresponding test files first
   - Follow Red-Green-Refactor pattern:
     - Write/update tests first (Red)
     - Implement code to make tests pass (Green)
     - Refactor while keeping tests green
   - Test files should mirror source file structure in tests/ directory

2. After ALL code changes:

   - Run tests for the specific module you modified:
     ```
     uv run pytest <module_directory>
     ```
   - Fix any test errors (warnings can be ignored)
   - If tests pass, proceed with commit
   - If tests fail, fix issues and rerun tests

3. Documentation:

   - Update relevant documentation if API changes
   - Add docstrings for new functions/classes
   - Update domain model if entity relationships change

4. Code Style:

   - Follow .editorconfig rules
   - Use type hints for all new code
   - Add comments for complex logic
   - Keep functions focused and small

5. After completing ANY task:
   - Run tests for the specific module you worked on:
     ```
     uv run pytest <module_directory>
     ```
   - Add a one-line summary to .cursor-updates in markdown
   - Report test status to user

If you forget, the user can type the command "finish" and you will run the tests for the appropriate module and update `.cursor-updates`.
