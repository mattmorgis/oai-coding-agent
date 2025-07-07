import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Callable, Optional

import typer

from oai_coding_agent import __version__
from oai_coding_agent.agent import (
    AgentProtocol,
    AsyncAgent,
    AsyncAgentProtocol,
    HeadlessAgent,
    HeadlessAgentProtocol,
)
from oai_coding_agent.console import GitHubConsole, OpenAIConsole
from oai_coding_agent.console.console import (
    ConsoleInterface,
    HeadlessConsole,
    ReplConsole,
)
from oai_coding_agent.logger import setup_logging
from oai_coding_agent.preflight import PreflightCheckError, run_preflight_checks
from oai_coding_agent.runtime_config import (
    GITHUB_TOKEN,
    OPENAI_API_KEY_ENV,
    OPENAI_BASE_URL_ENV,
    ModeChoice,
    ModelChoice,
    RuntimeConfig,
    load_envs,
)

# Global factory functions - set by create_app()
_agent_factory: Optional[Callable[[RuntimeConfig], AgentProtocol]] = None
_console_factory: Optional[Callable[[AgentProtocol], ConsoleInterface]] = None


def default_agent_factory(config: RuntimeConfig) -> AgentProtocol:
    """Default factory for creating Agent instances."""
    if config.prompt:
        return HeadlessAgent(config)
    else:
        return AsyncAgent(config)


def default_console_factory(agent: AgentProtocol) -> ConsoleInterface:
    """Default factory for creating ConsoleInterface instances."""
    if agent.config.prompt:
        if isinstance(agent, HeadlessAgentProtocol):
            return HeadlessConsole(agent)
        else:
            raise TypeError("HeadlessConsole requires HeadlessAgentProtocol")
    else:
        if isinstance(agent, AsyncAgentProtocol):
            return ReplConsole(agent)
        else:
            raise TypeError("ReplConsole requires AsyncAgentProtocol")


def create_github_cli_app() -> typer.Typer:
    # Create github subcommand group
    github_app = typer.Typer(rich_markup_mode=None)
    github_app.command("login")(github_login)
    github_app.command("logout")(github_logout)
    return github_app


def github_login() -> None:
    """Log in to GitHub using browser-based flow."""
    github_console = GitHubConsole()
    github_console.prompt_auth()
    # if not token:
    #     raise typer.Exit(code=1)


def github_logout() -> None:
    """Remove stored GitHub authentication token."""
    github_console = GitHubConsole()
    github_console.logout()


def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            help="Show the version and exit",
            is_eager=True,
        ),
    ] = False,
    openai_api_key: Annotated[
        Optional[str],
        typer.Option(
            envvar=OPENAI_API_KEY_ENV,
            help="OpenAI API key (optional; will prompt if missing)",
        ),
    ] = None,
    github_token: Annotated[
        Optional[str],
        typer.Option(
            envvar=GITHUB_TOKEN,
            help="GitHub Token",
        ),
    ] = None,
    model: Annotated[
        ModelChoice,
        typer.Option("--model", "-m", help="OpenAI model to use"),
    ] = ModelChoice.codex_mini_latest,
    mode: Annotated[
        ModeChoice,
        typer.Option(
            "--mode",
            help="Agent mode: default, async, or plan",
        ),
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
        typer.Option(
            envvar=OPENAI_BASE_URL_ENV,
            help="OpenAI base URL",
        ),
    ] = None,
    prompt: Annotated[
        Optional[str],
        typer.Option(
            "--prompt",
            "-p",
            help="Prompt text for non-interactive async mode; use '-' to read from stdin",
        ),
    ] = None,
    atlassian: Annotated[
        bool,
        typer.Option(
            "--atlassian",
            help="Enable Atlassian MCP server (only available in plan mode)",
        ),
    ] = False,
) -> None:
    """OAI CODING AGENT - starts an interactive session"""
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    # If no subcommand, run default action
    if ctx.invoked_subcommand is None:
        logger = logging.getLogger(__name__)

        if openai_api_key is None:
            openai_console = OpenAIConsole()
            openai_api_key = openai_console.prompt_auth()

        assert openai_api_key is not None, "OpenAI API key is required"

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
        if not github_token and mode == ModeChoice.default and not prompt:
            # Only prompt for browser auth in interactive Default mode
            github_console = GitHubConsole()

            token = github_console.prompt_auth()
            if token:
                github_token = token

        cfg = RuntimeConfig(
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            github_token=github_token,
            model=model,
            repo_path=repo_path,
            mode=ModeChoice.async_ if prompt else mode,  # run in async mode if prompt
            github_repo=github_repo,
            branch_name=branch_name,
            prompt=prompt_text,
            atlassian=atlassian,
        )

        if not prompt:
            logger.info(
                f"Starting chat with model {cfg.model.value} on repo {cfg.repo_path}"
            )
        else:
            logger.info(f"Running prompt in headless (async): {cfg.prompt}")

        try:
            factory = _agent_factory or default_agent_factory
            console_fact = _console_factory or default_console_factory
            agent = factory(cfg)
            agent_console = console_fact(agent)
            asyncio.run(agent_console.run())
        except KeyboardInterrupt:
            print("\nExiting...")


def create_app(
    agent_factory: Optional[Callable[[RuntimeConfig], AgentProtocol]] = None,
    console_factory: Optional[Callable[[AgentProtocol], ConsoleInterface]] = None,
) -> typer.Typer:
    """
    Create and configure the Typer application.

    Args:
        agent_factory: Factory function to create Agent instances
        console_factory: Factory function to create ConsoleInterface instances

    Returns:
        Typer application
    """
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info(
        f"OAI v{__version__} starting up (Python v{sys.version.split()[0]}, PID: {os.getpid()})"
    )

    # Load API keys and related settings from .env if not already set in the environment
    load_envs()

    if agent_factory is None:
        agent_factory = default_agent_factory
    if console_factory is None:
        console_factory = default_console_factory

    # Set global factory functions
    global _agent_factory, _console_factory
    _agent_factory = agent_factory
    _console_factory = console_factory

    app = typer.Typer(rich_markup_mode=None)
    github_cli_app = create_github_cli_app()
    app.add_typer(github_cli_app, name="github")

    app.callback(invoke_without_command=True)(main)

    return app


def run() -> None:
    """Entry point for the CLI."""
    app = create_app()
    app()


if __name__ == "__main__":
    run()
