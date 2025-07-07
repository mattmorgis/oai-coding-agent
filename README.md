# OAI Coding Agent

A terminal-based coding agent designed for lightweight, asynchronous development tasks. Unlike traditional coding agents that require constant steering, this agent can work independently or collaboratively, enabling developers to run entire agent fleets for parallel development workflows.

> **Status**: Work in progress, not yet stable.

## Getting Started

```
uv tool install oai-coding-agent
```

Navigate to your project

```
cd your-projects-repo
```

Start the agent

```
oai
oai --help
oai -p "tell me what you can do in 2-3 sentences"
```

## Overview

This agent is built on OpenAI's codex-mini model and supports three distinct modes that enable a progressive trust-building journey:

1. **Default Mode** - Interactive agent that checks in when decisions are needed
2. **Async Mode** - Fully autonomous agent that completes tasks independently
3. **Plan Mode** - Read-only brainstorming mode to create tasks for agent fleets

## Features

- **Agent Fleets** - Run multiple agents in parallel using git worktrees locally or GitHub runners in CI
- **Progressive Workflow** - Start interactive, build trust, then scale to autonomous agent fleets
- **Environment Integration** - Automatically loads `.env` files from your project directory
- **MCP Support** - Leverages Model Context Protocol for enhanced tool capabilities

## The Progressive Workflow

Most developers follow this natural progression:

1. **Start with Default Mode** - Get familiar with the agent's capabilities and build trust through interactive sessions
2. **Scale with Multiple Agents** - Run parallel agents using git worktrees for independent tasks
3. **Deploy Agent Fleets** - Use plan mode to design workflows, then spawn agents on GitHub runners for automated PR generation

## Installation

### 1. Clone and install

```bash
git clone https://github.com/MattMorgis/oai-coding-agent.git
cd oai-coding-agent
uv venv
```

## Usage

Navigate to any codebase and run:

```bash
oai [OPTIONS]
```

### Configure your environment

The agent will automatically load environment variables from your project's `.env` file. At minimum, you'll need:

```bash
# In your project directory (not the agent's directory)
echo "OPENAI_API_KEY=your-key-here" >> .env
```

Optional variables:

- `OPENAI_BASE_URL` - Custom OpenAI API endpoint

### Agent Modes

#### Default Mode (Interactive)

The agent works alongside you, checking in when decisions are needed:

```bash
oai  # or explicitly: oai --mode default
```

#### Async Mode (Autonomous)

The agent completes tasks independently, documenting assumptions and alternatives:

```bash
oai --mode async --prompt "Add error handling to all API endpoints"
```

#### Plan Mode (Brainstorming)

Read-only mode for designing tasks that async agents can execute:

```bash
oai --mode plan
```

### Running Agent Fleets

#### Local Fleet with Git Worktrees

```bash
# Create worktrees for parallel development
git worktree add -b feature-1 ../agent-1
git worktree add -b feature-2 ../agent-2

# Run agents in each worktree
cd ../agent-1 && oai --mode async --prompt "Implement user authentication"
cd ../agent-2 && oai --mode async --prompt "Add API rate limiting"
```

#### GitHub Runner Fleet

1. Use plan mode to create independent tasks
2. Agents spawn on GitHub runners
3. Review PRs in 5-20 minutes

### Common Options

- `--version, -v` — Show the version and exit

- `--model, -m <model>` — OpenAI model (default: `codex-mini-latest`)
- `--repo-path <path>` — Target repository (default: current directory)
- `--prompt, -p <text | ->` — Headless mode prompt (`-` for stdin)

## Testing

```bash
uv run pytest
```
