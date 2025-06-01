"""
Headless (non-interactive) mode for running a single prompt asynchronously.
"""

from pathlib import Path
from typing import Optional

from .agent import AgentSession
from .console.rendering import console as rich_console
from .console.rendering import render_message


async def headless_main(
    repo_path: Path,
    model: str,
    openai_api_key: str,
    github_personal_access_token: str,
    mode: str,
    prompt: str,
    github_repo: Optional[str] = None,
    branch_name: Optional[str] = None,
) -> None:
    """
    Execute one prompt in async 'headless' mode and render streamed output.

    Args:
        repo_path: Path to the repository to operate on.
        model: OpenAI model identifier.
        openai_api_key: API key for OpenAI.
        github_personal_access_token: GitHub Personal Access Token for GitHub MCP server.
        mode: Agent mode (should be 'async' for headless runs).
        prompt: The prompt text to send to the agent.
        github_repo: The GitHub repository in "owner/repo" format (if available).
        branch_name: The current git branch name (if available).
    """
    rich_console.print(f"[bold cyan]Prompt:[/bold cyan] {prompt}")
    async with AgentSession(
        repo_path=repo_path,
        model=model,
        openai_api_key=openai_api_key,
        github_personal_access_token=github_personal_access_token,
        mode=mode,
        github_repo=github_repo,
        branch_name=branch_name,
    ) as session_agent:
        ui_stream, _ = await session_agent.run_step(prompt)
        async for msg in ui_stream:
            render_message(msg)
