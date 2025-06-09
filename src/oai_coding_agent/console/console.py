import asyncio

# import time
from typing import Protocol

from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style

# from rich.live import Live
from rich.panel import Panel

from oai_coding_agent.agent import AgentProtocol
from oai_coding_agent.console.rendering import clear_terminal, console, render_message
from oai_coding_agent.console.slash_commands import (
    handle_slash_command,
    register_slash_commands,
)
from oai_coding_agent.console.state import UIState
from oai_coding_agent.console.ui_event_mapper import map_event_to_ui_message
from oai_coding_agent.runtime_config import get_data_dir


class Console(Protocol):
    """Common interface for console interactions."""

    agent: AgentProtocol

    async def run(self) -> None:
        pass


class HeadlessConsole:
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
            event_stream, _ = await self.agent.run(self.agent.config.prompt)
            async for event in event_stream:
                ui_msg = map_event_to_ui_message(event)
                if ui_msg:
                    render_message(ui_msg)


# Function to capture the output of console.print
def capture_rich_print(rich_content):
    with console.capture() as capture:
        console.print(rich_content)
    return capture.get()


class ReplConsole:
    """Console that runs interactive REPL mode."""

    def __init__(self, agent: AgentProtocol) -> None:
        self.agent = agent
        self.state = UIState()

        # Define the top section for read-only output
        self.top_section_content = FormattedTextControl(text="")
        top_section = Window(
            content=self.top_section_content,
            dont_extend_height=True,  # Height determined by content
        )

        # Store prompt history under the XDG data directory
        history_dir = get_data_dir()
        history_dir.mkdir(parents=True, exist_ok=True)
        history_path = history_dir / "prompt_history"

        # Define key bindings
        kb = KeyBindings()

        # Create a PromptSession for the bottom section
        self.prompt_session: PromptSession[str] = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
            complete_while_typing=True,
            completer=WordCompleter([f"/{c}" for c in self.state.slash_commands]),
            complete_in_thread=True,
            key_bindings=kb,
            style=Style.from_dict(
                {"prompt": "ansicyan bold", "auto-suggestion": "#888888"}
            ),
            erase_when_done=True,
        )

        # Define the bottom section for the prompt session
        bottom_section = Window(
            BufferControl(buffer=self.prompt_session.default_buffer),
            dont_extend_height=True,
        )

        # Combine the sections using HSplit
        container = HSplit(
            [
                top_section,
                bottom_section,
            ]
        )

        # Define the layout
        layout = Layout(container)

        # Create the application without full screen mode
        self.application = Application(layout=layout, full_screen=False)

    async def run(self) -> None:
        """Run the interactive console application."""
        clear_terminal()

        register_slash_commands(self.state)

        # Display welcome banner (printed to console, not in the app)
        console.print(
            Panel(
                f"[bold cyan]╭─ OAI CODING AGENT ─╮[/bold cyan]\n\n"
                f"[dim]Current Directory:[/dim] [dim cyan]{self.agent.config.repo_path}[/dim cyan]\n"
                f"[dim]Model:[/dim] [dim cyan]{self.agent.config.model.value}[/dim cyan]\n"
                f"[dim]Mode:[/dim] [dim cyan]{self.agent.config.mode.value}[/dim cyan]",
                expand=False,
            )
        )
        console.print()  # Add spacing

        # Function to update the top section with rich content
        def print_to_top_section(rich_content):
            ansi_content = capture_rich_print(rich_content)
            current_text = self.top_section_content.text
            new_text = (
                f"{current_text}\n{ansi_content}" if current_text else ansi_content
            )
            self.top_section_content.text = new_text

        # Function to simulate live updates
        # def simulate_live_updates():
        #     with Live(
        #         Panel("Initial content"), refresh_per_second=4, console=console
        #     ) as live:
        #         for i in range(10):
        #             live.update(Panel(f"Count: {i}"))
        #             time.sleep(1)
        #             print_to_top_section(Panel(f"Count: {i}"))

        # # Start simulating live updates
        # asyncio.sleep(10, simulate_live_updates())

        # await self.application.run_async()

        # Run the application with the agent context
        async with self.agent:
            continue_loop = True
            while continue_loop:
                try:
                    user_input = await asyncio.to_thread(
                        lambda: self.prompt_session.prompt("› ")
                    )
                    if not user_input.strip():
                        continue

                    if user_input.strip().lower() in ["exit", "quit", "/exit", "/quit"]:
                        continue_loop = self.state.slash_commands["exit"]("")
                        continue

                    if user_input.startswith("/"):
                        continue_loop = handle_slash_command(self.state, user_input)
                        continue

                    console.print(f"[dim]› {user_input}[/dim]\n")
                except (KeyboardInterrupt, EOFError):
                    continue_loop = False
