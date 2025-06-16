from typing import Protocol

from oai_coding_agent.agent import AgentProtocol
from oai_coding_agent.console.rendering import console, render_message
from oai_coding_agent.console.repl_console import ReplConsole
from oai_coding_agent.console.ui_event_mapper import map_event_to_ui_message

__all__ = ["ConsoleInterface", "HeadlessConsole", "ReplConsole"]


class ConsoleInterface(Protocol):
    """Common interface for console interactions."""

    agent: AgentProtocol

    async def run(self) -> None:
        pass


class HeadlessConsole(ConsoleInterface):
    """Console that runs headless (single prompt) mode."""

    def __init__(self, agent: AgentProtocol) -> None:
        self.agent = agent

    async def run(self) -> None:
        """
        Execute one prompt in async 'headless' mode and render streamed output.
        """
        if not self.agent.config.prompt:
            raise ValueError("Prompt is required for headless mode")

        console.print(f"[bold cyan]Prompt:[/bold cyan] {self.agent.config.prompt}")
        async with self.agent:
            event_stream = await self.agent.run(self.agent.config.prompt)
            async for event in event_stream:
                ui_msg = map_event_to_ui_message(event)
                if ui_msg:
                    render_message(ui_msg)


