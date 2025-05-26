import asyncio
import logging
import os
from .config import load_api_key_from_dotenv
from enum import Enum
from pathlib import Path

import typer

from rich.console import Console

from typing_extensions import Annotated

from . import rich_tui
from .logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

console = Console()

# Load OPENAI_API_KEY from .env if present
load_api_key_from_dotenv()


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
    repo_path: Path = typer.Option(
        None,
        "--repo-path",
        help="Path to the repository. This path (and its subdirectories) are the only files the agent has permission to access"
    ),
):
    """
    OAI CODING AGENT - starts an interactive session
    """
    if repo_path is None:
        repo_path = Path.cwd()

    logger.info(f"Starting chat with model {model.value} on repo {repo_path}")
    try:
        asyncio.run(rich_tui.main(repo_path, model.value, openai_api_key))
    except KeyboardInterrupt:
        console.print("\nExiting...")


if __name__ == "__main__":
    app()
