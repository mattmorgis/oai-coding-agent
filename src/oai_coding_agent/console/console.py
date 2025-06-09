import asyncio
from typing import Optional, Protocol

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
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
        self.live_output_buffer = Buffer(read_only=False)

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
            accept_handler=self._on_accept,
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
        # Use just our key bindings for now - TextArea will handle its own input
        merged_bindings = self.kb

        self.app: Application = Application(
            layout=Layout(root_container, focused_element=self.input_area),
            key_bindings=merged_bindings,
            style=Style.from_dict(
                {
                    "prompt": "ansicyan bold",
                }
            ),
            mouse_support=False,  # Disable mouse support to avoid terminal issues
            full_screen=False,
            enable_page_navigation_bindings=False,
            input=None,  # Use default input
            output=None,  # Use default output
        )

    def _on_accept(self, buffer) -> None:
        """Handle when Enter is pressed in the TextArea."""
        text = buffer.text.strip()
        if text and not self.is_processing:
            # Clear the buffer after getting the text
            buffer.reset()
            # Process the input
            asyncio.create_task(self._process_input(text))

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
                            plain_console.print(render_message(ui_msg))
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
                    console.print(render_message(msg))

                # Clear live area after successful completion
                self.live_output_buffer.text = ""

            except asyncio.CancelledError:
                if self.interrupted:
                    # Print partial output to console
                    for msg in full_response:
                        console.print(render_message(msg))

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
