import asyncio
from typing import Optional, Protocol

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea
from rich.panel import Panel

from oai_coding_agent.agent import AgentProtocol
from oai_coding_agent.console.rendering import clear_terminal, console, render_message
from oai_coding_agent.console.slash_commands import (
    handle_slash_command,
    register_slash_commands,
)
from oai_coding_agent.console.state import UIState
from oai_coding_agent.console.ui_event_mapper import map_event_to_ui_message


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


class ReplConsole:
    """Console that runs interactive REPL mode."""

    def __init__(self, agent: AgentProtocol) -> None:
        self.agent = agent
        self.state = UIState()
        self.stream_task: Optional[asyncio.Task] = None
        self.interrupted = False
        self.is_processing = False

        # Buffer for live streaming output
        self.live_output_buffer = Buffer(read_only=True)

        # Create the live output area (for streaming responses)
        self.live_output_area = Window(
            content=BufferControl(buffer=self.live_output_buffer),
            height=10,  # Fixed height for live area
            wrap_lines=True,
        )

        # Create the input area
        self.input_area = TextArea(
            height=1,
            multiline=False,
            wrap_lines=False,
            focusable=True,
            prompt="› ",
        )

        # Create key bindings
        self.kb = self._create_key_bindings()

        # Create layout: live output + separator + input
        root_container = HSplit(
            [
                self.live_output_area,
                Window(height=1, char="─"),
                self.input_area,
            ]
        )

        # Create application (not full screen to use terminal scrolling)
        self.app: Application = Application(
            layout=Layout(root_container),
            key_bindings=self.kb,
            style=Style.from_dict(
                {
                    "prompt": "ansicyan bold",
                }
            ),
            mouse_support=True,
            full_screen=False,
        )

    def _create_key_bindings(self) -> KeyBindings:
        """Create key bindings for the console."""
        kb = KeyBindings()

        @kb.add("c-c")
        def handle_interrupt(event):
            """Handle Ctrl-C to interrupt streaming or clear input."""
            if self.is_processing and self.stream_task:
                self.interrupted = True
                self.stream_task.cancel()
                # Add interruption message to live area (will be cleared on next input)
                self.live_output_buffer.text = (
                    self.live_output_buffer.text + "\n⏹ Interrupted\n"
                )
            else:
                event.app.current_buffer.reset()

        @kb.add("c-d")
        def handle_exit(event):
            """Handle Ctrl-D to exit."""
            event.app.exit()

        @kb.add("enter")
        def handle_enter(event):
            """Handle Enter to submit input."""
            if not self.is_processing:
                text = event.app.current_buffer.text.strip()
                if text:
                    event.app.current_buffer.reset()
                    asyncio.create_task(self._process_input(text))

        return kb

    async def _process_input(self, user_input: str) -> None:
        """Process user input asynchronously."""
        try:
            self.is_processing = True

            # Handle exit commands
            if user_input.lower() in ["exit", "quit", "/exit", "/quit"]:
                self.app.exit()
                return

            # Handle slash commands
            if user_input.startswith("/"):
                if not handle_slash_command(self.state, user_input):
                    self.app.exit()
                return

            # Clear the live output area for new response
            self.live_output_buffer.text = ""

            # Print user input to console (this becomes part of the permanent history)
            console.print(f"[dim]› {user_input}[/dim]\n")

            # Snapshot last response ID for recovery
            last_completed_id = getattr(self.agent, "_previous_response_id", None)

            # Run the agent
            event_stream, result = await self.agent.run(user_input)

            # Buffer to collect the complete response
            full_response = []

            # Consume event stream
            async def _consume_stream():
                buffer_text = ""
                async for event in event_stream:
                    ui_msg = map_event_to_ui_message(event)
                    if ui_msg:
                        # For live area, we need plain text
                        from rich.console import Console as RichConsole

                        # First capture the rich output for final display
                        full_response.append(ui_msg)

                        # Then get plain text for live area
                        plain_console = RichConsole(
                            force_terminal=False, no_color=True, width=80
                        )
                        with plain_console.capture() as capture:
                            render_message(ui_msg, console=plain_console)
                        plain_text = capture.get()

                        if plain_text:
                            buffer_text += plain_text
                            # Update live area
                            self.live_output_buffer.text = buffer_text

            self.interrupted = False
            self.stream_task = asyncio.create_task(_consume_stream())

            try:
                await self.stream_task

                # Stream completed successfully - print final output to console
                for msg in full_response:
                    render_message(msg)

                # Clear live area after successful completion
                self.live_output_buffer.text = ""

            except asyncio.CancelledError:
                if self.interrupted:
                    # Print partial output to console
                    for msg in full_response:
                        render_message(msg)

                    # Cancel the result future
                    result.cancel()

                    # Restore previous response ID
                    if hasattr(self.agent, "_previous_response_id"):
                        self.agent._previous_response_id = last_completed_id

                    # Keep interrupted message in live area (will be cleared on next input)
            finally:
                self.stream_task = None

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            self.live_output_buffer.text = ""
        finally:
            self.is_processing = False

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

        # Run the application with the agent context
        async with self.agent:
            await self.app.run_async()
