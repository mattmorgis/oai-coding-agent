# oai-coding-agent

An interactive coding assistant built with the OpenAI Agents SDK and Model Context Protocol (MCP) for exploring and interacting with a local codebase.

---

## Prerequisites

- **Python** ≥ 3.11
- **Node.js** & **npx** (required to launch the MCP filesystem server)
- **uv** for dependency management and task running

## Installation

Install the package and its dependencies:

```bash
uv sync
```

This installs the `oai` command-line tool.

## Usage

### Command-Line Interface

The main entry point is the `oai` command:

```bash
# Start interactive chat (default command)
oai

# Start chat with specific model
oai --model o3

# Start chat with specific repository path
oai --repo-path /path/to/your/repo

# Show configuration
oai config
```

Available models:

- `o3` (default)
- `o4-mini`
- `codex-mini-latest`

The chat interface provides:

1. An MCP filesystem server (via `npx @modelcontextprotocol/server-filesystem`) for accessing your codebase
2. CLI tools including grep for powerful code searching (via `cli-mcp-server`)
3. An interactive chat UI with syntax highlighting and markdown rendering
4. Automatic conversation history management

## Environment Variables

Set your OpenAI API key in a `.env` file:

```bash
cp .env-example .env
```

Required variables:

- `OPENAI_API_KEY`: Your OpenAI API key

Optional variables:

- `ENABLE_CLI_TOOLS`: Set to "false" to disable grep/CLI tools (default: "true")
- `CLI_ALLOW_ALL_FLAGS`: Set to "true" to allow all command flags (default: "false", uses a curated list of common flags)

## Using Grep and CLI Tools

When `ENABLE_CLI_TOOLS` is set to "true" (default), the agent has access to powerful command-line tools including:

- `grep` - Search for patterns in files
- `rg` (ripgrep) - Fast recursive grep
- `find` - Find files and directories
- `ls`, `cat`, `head`, `tail`, `wc` - Basic file operations

Example queries you can ask:
- "Search for all occurrences of 'AgentSession' in the codebase"
- "Find all Python files that import 'asyncio'"
- "Use grep to find TODO comments"
- "Search for functions that handle errors"

The CLI tools are sandboxed to only operate within your specified repository path for security.

## Development

Install development dependencies and set up pre-commit hooks to automatically
format staged files with `ruff`:

```bash
uv sync --dev
pre-commit install
```

Running `pre-commit install` ensures that every commit formats staged Python
files using `ruff`.
