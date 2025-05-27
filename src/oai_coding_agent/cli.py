import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from typing import Optional
from typing_extensions import Annotated

from .config import Config, ModelChoice, ModeChoice
from .console.repl import main as console_main
from .agent import AgentSession
from .console.rendering import console as rich_console, render_message
from .logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Local console for CLI messages (e.g., exit)
console = Console()

app = typer.Typer(rich_markup_mode=None)


async def batch_main(
    repo_path: Path,
    model: str,
    openai_api_key: str,
    mode: str,
    prompt: str,
) -> None:
    """
    Run a single prompt in non-interactive mode.
    """
    rich_console.print(f"[bold cyan]Prompt:[/bold cyan] {prompt}")
    async with AgentSession(
        repo_path=repo_path,
        model=model,
        openai_api_key=openai_api_key,
        mode=mode,
    ) as session_agent:
        ui_stream, result = await session_agent.run_step(prompt)
        async for msg in ui_stream:
            render_message(msg)


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
    cfg = Config.from_cli(openai_api_key, model, repo_path, mode)

    if prompt:
        logger.info(f"Running prompt in batch mode: {prompt}")
        try:
            asyncio.run(
                batch_main(
                    cfg.repo_path,
                    cfg.model.value,
                    cfg.openai_api_key,
                    cfg.mode.value,
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
                cfg.repo_path, cfg.model.value, cfg.openai_api_key, cfg.mode.value
            )
        )
    except KeyboardInterrupt:
        console.print("\nExiting...")


if __name__ == "__main__":
    app()
