import asyncio
import logging
import sys
from pathlib import Path
from typing import Callable, Optional

import typer
from typing_extensions import Annotated

from .agent import Agent, AgentProtocol
from .auth.github_browser_auth import authenticate_github_browser
from .auth.token_storage import (
    load_auth_to_environment,
)
from .console.console import Console, HeadlessConsole, ReplConsole
from .logger import setup_logging
from .preflight import PreflightCheckError, run_preflight_checks
from .runtime_config import (
    GITHUB_PERSONAL_ACCESS_TOKEN_ENV,
    OPENAI_API_KEY_ENV,
    OPENAI_BASE_URL_ENV,
    ModeChoice,
    ModelChoice,
    RuntimeConfig,
    load_envs,
)


def default_agent_factory(config: RuntimeConfig) -> AgentProtocol:
    """Default factory for creating Agent instances."""
    return Agent(config)


def default_console_factory(agent: AgentProtocol) -> Console:
    """Default factory for creating Console instances."""
    if agent.config.prompt:
        return HeadlessConsole(agent)
    else:
        return ReplConsole(agent)


def create_app(
    agent_factory: Optional[Callable[[RuntimeConfig], AgentProtocol]] = None,
    console_factory: Optional[Callable[[AgentProtocol], Console]] = None,
) -> typer.Typer:
    """
    Create and configure the Typer application.

    Args:
        agent_factory: Factory function to create Agent instances
        console_factory: Factory function to create Console instances

    Returns:
        Typer application
    """
    if agent_factory is None:
        agent_factory = default_agent_factory
    if console_factory is None:
        console_factory = default_console_factory

    app = typer.Typer(rich_markup_mode=None)

    @app.command()
    def main(
        openai_api_key: Annotated[
            str, typer.Option(envvar=OPENAI_API_KEY_ENV, help="OpenAI API key")
        ],
        github_personal_access_token: Annotated[
            Optional[str],
            typer.Option(
                envvar=GITHUB_PERSONAL_ACCESS_TOKEN_ENV,
                help="GitHub Personal Access Token",
            ),
        ] = None,
        model: Annotated[
            ModelChoice, typer.Option("--model", "-m", help="OpenAI model to use")
        ] = ModelChoice.codex_mini_latest,
        mode: Annotated[
            ModeChoice,
            typer.Option("--mode", help="Agent mode: default, async, or plan"),
        ] = ModeChoice.default,
        repo_path: Path = typer.Option(
            Path.cwd(),
            "--repo-path",
            help=(
                "Path to the repository. This path (and its subdirectories) "
                "are the only files the agent has permission to access"
            ),
        ),
        openai_base_url: Annotated[
            Optional[str],
            typer.Option(envvar=OPENAI_BASE_URL_ENV, help="OpenAI base URL"),
        ] = None,
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
        # Load authentication from ~/.oai/auth file into environment
        load_auth_to_environment()

        setup_logging()
        logger = logging.getLogger(__name__)

        # Run preflight checks and get git info
        try:
            github_repo, branch_name = run_preflight_checks(repo_path)
        except PreflightCheckError as e:
            for error in e.errors:
                typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(code=1)

        # Read prompt text if provided
        prompt_text = None
        if prompt:
            if prompt == "-":
                prompt_text = sys.stdin.read()
            else:
                prompt_text = prompt

        # Handle GitHub authentication
        if (
            not github_personal_access_token
            and mode == ModeChoice.default
            and not prompt
        ):
            # Only prompt for browser auth in interactive Default mode
            typer.echo("\n⚠️  No GitHub Personal Access Token found.")
            typer.echo("Would you like to authenticate with GitHub using your browser?")
            if typer.confirm("Authenticate now?"):
                token = authenticate_github_browser()
                if token:
                    github_personal_access_token = token
                else:
                    typer.echo("\n❌ Browser authentication failed.")
                    typer.echo("Please set GITHUB_PERSONAL_ACCESS_TOKEN_ENV manually.")
                    raise typer.Exit(code=1)
            else:
                typer.echo("\nAlternatively, you can:")
                typer.echo(
                    "  • Set environment variable: export GITHUB_PERSONAL_ACCESS_TOKEN_ENV=your_token"
                )
                typer.echo(
                    "  • Use command line option: --github-personal-access-token your_token"
                )
                typer.echo("  • The agent will continue without GitHub integration")

        # Note: github_personal_access_token can be None - the agent will handle this gracefully

        cfg = RuntimeConfig(
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
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
            agent = agent_factory(cfg)
            console = console_factory(agent)
            asyncio.run(console.run())
        except KeyboardInterrupt:
            print("\nExiting...")

    return app


# Load API keys and related settings from .env if not already set in the environment
load_envs()

# Create default app instance for backward compatibility
app = create_app()

if __name__ == "__main__":
    app()
