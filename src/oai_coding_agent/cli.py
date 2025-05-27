import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from typing_extensions import Annotated

from .config import Config, ModelChoice, ModeChoice
from .console.repl import main as console_main
from .logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

console = Console()

app = typer.Typer(rich_markup_mode=None)


@app.command()
def main(
    openai_api_key: Annotated[
        str, typer.Option(envvar="OPENAI_API_KEY", help="OpenAI API key")
    ],
    model: Annotated[
        ModelChoice, typer.Option("--model", "-m", help="OpenAI model to use")
    ] = ModelChoice.codex_mini_latest,
    mode: Annotated[
        ModeChoice, typer.Option("--mode", help="Agent mode: default, async, or plan")
    ] = ModeChoice.default,
    repo_path: Path = typer.Option(
        None,
        "--repo-path",
        help="Path to the repository. This path (and its subdirectories) are the only files the agent has permission to access",
    ),
) -> None:
    """
    OAI CODING AGENT - starts an interactive session
    """
    # Build a single config object from the CLI parameters
    cfg = Config.from_cli(openai_api_key, model, repo_path, mode)

    logger.info(f"Starting chat with model {cfg.model.value} on repo {cfg.repo_path}")
    try:
        asyncio.run(
            console_main(
                cfg.repo_path, cfg.model.value, cfg.openai_api_key, cfg.mode.value
            )
        )
    except KeyboardInterrupt:
        console.print("\nExiting...")


if __name__ == "__main__":
    app()
