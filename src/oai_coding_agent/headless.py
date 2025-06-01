"""
Headless (non-interactive) mode for running a single prompt asynchronously.
"""

from pathlib import Path

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
    """
    rich_console.print(f"[bold cyan]Prompt:[/bold cyan] {prompt}")
    async with AgentSession(
        repo_path=repo_path,
        model=model,
        openai_api_key=openai_api_key,
        github_personal_access_token=github_personal_access_token,
        mode=mode,
    ) as session_agent:
        ui_stream, _ = await session_agent.run_step(prompt)
        async for msg in ui_stream:
            render_message(msg)
