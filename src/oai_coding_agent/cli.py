import asyncio
import logging
import os
from enum import Enum
from pathlib import Path

import typer
from dotenv import dotenv_values
from rich.console import Console
from typing_extensions import Annotated

from . import rich_tui
from .logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

console = Console()

# Ensure OPENAI_API_KEY is loaded from .env if present
# This is a convenience method, most developers will be launching this from their own projects.
# We only want to load OPENAI_API_KEY and not read any other their other variables.
env_values = dotenv_values()
if "OPENAI_API_KEY" in env_values and env_values["OPENAI_API_KEY"] is not None:
    os.environ["OPENAI_API_KEY"] = str(env_values["OPENAI_API_KEY"])


class ModelChoice(str, Enum):
    codex_mini_latest = "codex-mini-latest"
    o3 = "o3"
    o4_mini = "o4-mini"


app = typer.Typer()


@app.command()
def main(
    openai_api_key: Annotated[
        str, typer.Option(envvar="OPENAI_API_KEY", help="OpenAI API key")
    ],
    model: Annotated[
        ModelChoice, typer.Option("--model", "-m", help="OpenAI model to use")
    ] = ModelChoice.codex_mini_latest,
    repo_path: Annotated[
        Path,
        typer.Option(
            help="Path to the repository. This path (and its subdirectories) are the only files the agent has permission to access"
        ),
    ] = Path.cwd(),
):
    """
    OAI CODING AGENT - starts an interactive session
    """
    logger.info(f"Starting chat with model {model.value} on repo {repo_path}")
    try:
        asyncio.run(rich_tui.main(repo_path, model.value, openai_api_key))
    except KeyboardInterrupt:
        console.print("\nExiting...")


if __name__ == "__main__":
    app()
