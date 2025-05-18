# oai-coding-agent

An interactive coding assistant built with the OpenAI Agents SDK and Model Context Protocol (MCP) for exploring and interacting with a local codebase.

---

## Prerequisites

- **Python** ≥ 3.11
- **Node.js** & **npx** (required to launch the MCP filesystem server)
- **uv** for dependency management and task running

## Installation

Install the runtime dependencies listed in `pyproject.toml`:

```bash
uv sync
```

## Usage

Run the interactive coding agent:

```bash
uv run main.py
```

This will:

1. Launch an MCP filesystem server (via `npx @modelcontextprotocol/server-filesystem`) pointed at your local directory.
2. Start an interactive REPL where you can ask questions and issue commands to explore your code.
3. Automatically manage conversation history across turns.

Once running, you can type your question or command at the `You:` prompt. Be sure to enter your local repo path. Enter `exit`, `quit`, or `bye` to end the session.

## Customization

- **Mounted directory**: By default, `main.py` mounts `/Users/matt/Developer/`. Edit the `MCPServerStdio` parameters in `main.py` to point to your own code folder.
