import asyncio
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from typing_extensions import Annotated

from .config import Config, ModeChoice, ModelChoice
from .console.rendering import console as rich_console
from .console.repl import main as console_main
from .headless import headless_main
from .logger import setup_logging
from .preflight import run_preflight_checks

setup_logging()
logger = logging.getLogger(__name__)

# Local console for CLI messages (e.g., exit)
console = Console()

app = typer.Typer(rich_markup_mode=None)


@app.command()
def main(
    openai_api_key: Annotated[
        str, typer.Option(envvar="OPENAI_API_KEY", help="OpenAI API key")
    ],
    github_personal_access_token: Annotated[
        str,
        typer.Option(
            envvar="GITHUB_PERSONAL_ACCESS_TOKEN",
            help="GitHub Personal Access Token",
        ),
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
        help=(
            "Path to the repository. This path (and its subdirectories) "
            "are the only files the agent has permission to access"
        ),
    ),
    prompt: Annotated[
        Optional[str],
        typer.Option(
            "--prompt",
            "-p",
            help="Prompt to run in non-interactive mode",
        ),
    ] = None,
) -> None:
    """
    OAI CODING AGENT - starts an interactive or batch session
    """
    # Build a single config object from the CLI parameters
    cfg = Config.from_cli(
        openai_api_key,
        github_personal_access_token,
        model,
        repo_path,
        mode,
    )
    run_preflight_checks(cfg.repo_path)

    if prompt:
        # Force async mode for one-off prompt runs
        mode_value = ModeChoice.async_.value
        logger.info(f"Running prompt in headless (async): {prompt}")
        try:
            asyncio.run(
                headless_main(
                    cfg.repo_path,
                    cfg.model.value,
                    cfg.openai_api_key,
                    cfg.github_personal_access_token,
                    mode_value,
                    prompt,
                )
            )
        except KeyboardInterrupt:
            rich_console.print("\nExiting...")
        return

    logger.info(f"Starting chat with model {cfg.model.value} on repo {cfg.repo_path}")
    try:
        asyncio.run(
            console_main(
                cfg.repo_path,
                cfg.model.value,
                cfg.openai_api_key,
                cfg.github_personal_access_token,
                cfg.mode.value,
            )
        )
    except KeyboardInterrupt:
        console.print("\nExiting...")


if __name__ == "__main__":
    app()
