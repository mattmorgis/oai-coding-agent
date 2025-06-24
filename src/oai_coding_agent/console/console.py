from typing import Protocol

from oai_coding_agent.agent import HeadlessAgentProtocol
from oai_coding_agent.console.rendering import console, render_event
from oai_coding_agent.console.repl_console import ReplConsole

__all__ = ["ConsoleInterface", "HeadlessConsole", "ReplConsole"]


class ConsoleInterface(Protocol):
    """Common interface for console interactions."""

    async def run(self) -> None:
        pass


class HeadlessConsole(ConsoleInterface):
    """Console that runs headless (single prompt) mode."""

    agent: HeadlessAgentProtocol

    def __init__(self, agent: HeadlessAgentProtocol) -> None:
        self.agent = agent

    async def run(self) -> None:
        """
        Execute one prompt in async 'headless' mode and render streamed output.
        """
        if not self.agent.config.prompt:
            raise ValueError("Prompt is required for headless mode")

        console.print(f"[bold cyan]Prompt:[/bold cyan] {self.agent.config.prompt}")
        async with self.agent:
            try:
                async for event in self.agent.run(self.agent.config.prompt):
                    render_event(event)
            except KeyboardInterrupt:
                # Cancel agent gracefully on interrupt
                await self.agent.cancel()
                raise
