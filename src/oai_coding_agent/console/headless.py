"""
Headless (non-interactive) mode for running a single prompt asynchronously.
"""

from ..agent import AgentSession
from ..runtime_config import RuntimeConfig
from .rendering import console as rich_console
from .rendering import render_message


async def headless_main(config: RuntimeConfig, prompt: str) -> None:
    """
    Execute one prompt in async 'headless' mode and render streamed output.

    Args:
        config: Runtime configuration for the agent.
        prompt: The prompt text to send to the agent.
    """
    rich_console.print(f"[bold cyan]Prompt:[/bold cyan] {prompt}")
    async with AgentSession(config) as session_agent:
        ui_stream, _ = await session_agent.run_step(prompt)
        async for msg in ui_stream:
            render_message(msg)
