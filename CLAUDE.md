# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an interactive coding agent built with the OpenAI Agents SDK and Model Context Protocol (MCP) for exploring and interacting with a local codebase. The agent is implemented as both a command-line interface (CLI) and a text-based user interface (TUI).

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