# OAI Coding Agent

An interactive command-line AI assistant for exploring, understanding, and editing code using the OpenAI Agents SDK and the Model Context Protocol (MCP).

## Features

- **Interactive REPL** powered by `prompt-toolkit` and `Rich` for smooth AI-driven coding assistance
- **Headless mode** for running one-off prompts non-interactively
- **Dynamic mode selection**: `default`, `async`, or `plan` to suit different workflows

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/oai-coding-agent.git
cd oai-coding-agent
```

### 2. Configure environment variables

Copy the example file and set your OpenAI API key:

```bash
cp .env-example .env
# Edit .env and set OPENAI_API_KEY and GITHUB_PERSONAL_ACCESS_TOKEN (and other variables as needed)
```

> **Tip:** Instead of creating a new token on GitHub.com, you can quickly export one with:

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN=$(gh auth token)
```

### 3. Install dependencies

Using `uv` (recommended):

```bash
uv sync
```

## Usage

### Interactive mode

Launch the REPL and start chatting:

```bash
uv run oai [OPTIONS]
```

Common options:

- `--model, -m <model>` — OpenAI model to use (default: `codex-mini-latest`)
- `--mode <mode>` — Agent mode: `default`, `async`, or `plan` (default: `default`)
- `--repo-path <path>` — Path to the repository (default: current directory)
- `--prompt, -p <text|->` — Run a one-off prompt in headless async mode (use `-` to read from stdin)

See [docs/cli.md](docs/cli.md) for full CLI reference and a flow diagram.

### Headless mode

Run a single prompt non-interactively:

```bash
# Literal prompt
uv run oai --prompt "Explain this function in simple terms."

# From stdin (for huge inputs / GitHub Actions)
echo "${{ github.event.issue.body }}" | uv run oai --prompt -
```

## Testing

Run the test suite with:

```bash
uv run pytest
```
