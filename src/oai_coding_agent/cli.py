import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from .console.console import main as console_main
from .logger import setup_logging
from .preflight import run_preflight_checks
from .runtime_config import (
    GITHUB_PERSONAL_ACCESS_TOKEN_ENV,
    OPENAI_API_KEY_ENV,
    ModeChoice,
    ModelChoice,
    RuntimeConfig,
    load_envs,
)

# Load API keys from .env if not already set in the environment
load_envs()

app = typer.Typer(rich_markup_mode=None)


@app.command()
def main(
    openai_api_key: Annotated[
        str, typer.Option(envvar=OPENAI_API_KEY_ENV, help="OpenAI API key")
    ],
    github_personal_access_token: Annotated[
        str,
        typer.Option(
            envvar=GITHUB_PERSONAL_ACCESS_TOKEN_ENV,
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
        Path.cwd(),
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
            help="Prompt text for non-interactive async mode; use '-' to read from stdin",
        ),
    ] = None,
) -> None:
    """
    OAI CODING AGENT - starts an interactive or batch session
    """
    setup_logging()
    logger = logging.getLogger(__name__)

    # Run preflight checks and get git info
    github_repo, branch_name = run_preflight_checks(repo_path)

    # Read prompt text if provided
    prompt_text = None
    if prompt:
        if prompt == "-":
            prompt_text = sys.stdin.read()
        else:
            prompt_text = prompt

    cfg = RuntimeConfig(
        openai_api_key=openai_api_key,
        github_personal_access_token=github_personal_access_token,
        model=model,
        repo_path=repo_path,
        mode=ModeChoice.async_ if prompt else mode,  # run in async mode if prompt
        github_repo=github_repo,
        branch_name=branch_name,
        prompt=prompt_text,
    )

    if not prompt:
        logger.info(
            f"Starting chat with model {cfg.model.value} on repo {cfg.repo_path}"
        )
    else:
        logger.info(f"Running prompt in headless (async): {cfg.prompt}")

    try:
        asyncio.run(console_main(cfg))
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    app()
