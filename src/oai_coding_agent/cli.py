import asyncio
import os
from enum import Enum
from pathlib import Path

import typer
from dotenv import dotenv_values
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from . import rich_tui

console = Console()

# Only ensure OPENAI_API_KEY is set in .env before loading other variables.  # Testing ruff-format hook.
# Testing trailing whitespace.
env_values = dotenv_values()
if "OPENAI_API_KEY" in env_values and env_values["OPENAI_API_KEY"] is not None:
    os.environ["OPENAI_API_KEY"] = str(env_values["OPENAI_API_KEY"])


class ModelChoice(str, Enum):
    codex_mini_latest = "codex-mini-latest"
    o3 = "o3"
    o4_mini = "o4-mini"


def config_table(model: ModelChoice, repo_path: Path) -> Table:
    table = Table()
    table.show_header = False
    table.show_lines = True
    table.add_row(
        "Model",
        model.value,
    )
    table.add_row("Repo Path", str(repo_path))

    return table


app = typer.Typer()


@app.command()
def config(
    openai_api_key: Annotated[str, typer.Option(envvar="OPENAI_API_KEY")],
    model: Annotated[
        ModelChoice, typer.Option("--model", "-m", help="OpenAI model to use")
    ] = ModelChoice.o3,
    repo_path: Annotated[
        Path,
        typer.Option(
            help="Path to the repository. This path (and it's subdirectories) are the only files the agent has permission to access"
        ),
    ] = Path.cwd(),
):
    """Show configuration information."""
    table = config_table(model, repo_path)
    console.print(table)


@app.command()
def chat(
    openai_api_key: Annotated[
        str, typer.Option(envvar="OPENAI_API_KEY", help="OpenAI API key")
    ],
    model: Annotated[
        ModelChoice, typer.Option("--model", "-m", help="OpenAI model to use")
    ] = ModelChoice.o3,
    repo_path: Annotated[
        Path,
        typer.Option(
            help="Path to the repository. This path (and it's subdirectories) are the only files the agent has permission to access"
        ),
    ] = Path.cwd(),
):
    """Start a chat session"""
    console.print(f"Starting chat with model {model.value} on repo {repo_path}")
    try:
        asyncio.run(rich_tui.main(repo_path, model.value, openai_api_key))
    except KeyboardInterrupt:
        console.print("\nExiting...")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    openai_api_key: Annotated[
        str, typer.Option(envvar="OPENAI_API_KEY", help="OpenAI API key")
    ],
    model: Annotated[
        ModelChoice, typer.Option("--model", "-m", help="OpenAI model to use")
    ] = ModelChoice.o3,
    repo_path: Annotated[
        Path,
        typer.Option(
            help="Path to the repository. This path (and it's subdirectories) are the only files the agent has permission to access"
        ),
    ] = Path.cwd(),
):
    """
    Start chatting with your codebase.
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(chat, openai_api_key, model, repo_path)


if __name__ == "__main__":
    app()
