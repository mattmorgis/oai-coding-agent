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

# Start chat in asynchronous autonomous mode
oai --mode async

# Start chat in planning mode
oai --mode plan

# Run a one-off prompt in non-interactive (async) mode
oai --prompt "<some task>"

# Passing a file as a prompt (async mode)
oai --prompt <task.md>  # the contents of task.md will be used as the prompt

# Headless (async) mode examples
# Running a literal prompt:
oai --prompt "Summarize this repo" --repo-path .

# Running a prompt from a file:
echo "Summarize this repo" > prompt.txt
oai --prompt prompt.txt --repo-path .
```

Available models:

- `o3`
- `o4-mini`
- `codex-mini-latest` (default)

Available modes:

- `default` (interactive collaborative mode)
- `async` (autonomous asynchronous mode)
- `plan` (architecture planning mode)


The chat interface provides:

1. An MCP filesystem server (via `npx @modelcontextprotocol/server-filesystem`) for accessing your codebase
2. CLI tools including grep for powerful code searching (via `cli-mcp-server`)
3. An interactive chat UI with syntax highlighting and markdown rendering

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

## Running Tests

```bash
uv run pytest
```

This will output a coverage summary in the terminal. For an HTML report, use `--cov-report html`.
