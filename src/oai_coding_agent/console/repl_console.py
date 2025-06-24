import asyncio
import logging
from typing import Optional

from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.filters import has_completions
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Dimension, HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea
from rich.panel import Panel

from oai_coding_agent.agent import AsyncAgentProtocol
from oai_coding_agent.console.rendering import console, render_event
from oai_coding_agent.runtime_config import get_data_dir

logger = logging.getLogger(__name__)


class Spinner:
    def __init__(self) -> None:
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.frame_index = 0
        self.is_spinning = False

    def start(self) -> None:
        """Start spinning."""
        self.is_spinning = True
        self.frame_index = 0

    def stop(self) -> None:
        """Stop spinning."""
        self.is_spinning = False

    def update(self) -> None:
        """Update spinner frame."""
        self.frame_index = (self.frame_index + 1) % len(self.frames)

    @property
    def current_frame(self) -> str:
        return self.frames[self.frame_index]


class ReplConsole:
    """Console that runs interactive REPL mode."""

    agent: AsyncAgentProtocol
    app: Optional[Application[None]]

    _render_task: Optional[asyncio.Task[None]]
    _should_stop_render: bool

    def __init__(self, agent: AsyncAgentProtocol) -> None:
        self.agent = agent

        # Create live status area (1 line, non-focusable; shows spinner "thinking..." or bullet "idle")
        self._live_status_control = FormattedTextControl(
            text="", focusable=False, show_cursor=False
        )
        self._live_status_area = Window(
            content=self._live_status_control,
            height=Dimension.exact(1),
            wrap_lines=False,
            style="class:live-status",
        )

        # Create prompt area (single line input)
        self._prompt_area = TextArea(
            prompt=HTML("<ansicyan><b>› </b></ansicyan>"),
            multiline=True,
            wrap_lines=True,
        )
        self.app = None
        self._spinner = Spinner()
        self._render_task = None
        self._should_stop_render = False

    async def _render_loop(self) -> None:
        """Main render loop - updates live area based on agent state."""
        try:
            while not self._should_stop_render:
                if self.agent.is_processing:
                    # Update spinner and show live area
                    self._spinner.update()
                    spinner_frame = self._spinner.current_frame
                    formatted_text = HTML(
                        f"<ansicyan>{spinner_frame} thinking...</ansicyan> "
                        f"(<ansigray><b>ESC</b></ansigray> to interrupt)\n"
                    )
                    self._live_status_control.text = formatted_text
                else:
                    # Always show an "idle" line when not processing
                    formatted_text = HTML("")
                    self._live_status_control.text = formatted_text

                if self.app:
                    self.app.invalidate()

                await asyncio.sleep(0.1)  # 10 FPS
        except asyncio.CancelledError:
            pass

    def _start_render_loop(self) -> None:
        """Start the render loop."""
        if not self._render_task or self._render_task.done():
            self._should_stop_render = False
            self._render_task = asyncio.create_task(self._render_loop())

    def _stop_render_loop(self) -> None:
        """Stop the render loop."""
        self._should_stop_render = True
        if self._render_task and not self._render_task.done():
            self._render_task.cancel()

    async def _event_stream_consumer(self) -> None:
        while True:
            agent_event = await self.agent.events.get()
            await run_in_terminal(lambda: render_event(agent_event))

    def _get_key_bindings(self) -> KeyBindings:
        """Return the custom KeyBindings (e.g. Tab behaviour)."""
        kb = KeyBindings()

        @kb.add("enter", filter=has_completions)
        def _(event: KeyPressEvent) -> None:
            buffer = event.current_buffer
            suggestion = buffer.suggestion
            if suggestion:
                buffer.insert_text(suggestion.text)
            else:
                buffer.complete_next()

        @kb.add("escape")
        async def _(event: KeyPressEvent) -> None:
            """Handle ESC - cancel current job."""
            await self.agent.cancel()
            await run_in_terminal(
                lambda: console.print(
                    "[bold red]error: Agent cancelled by user[/bold red]"
                )
            )

        # Support Ctrl+J for newline without submission.
        @kb.add("c-j", eager=True)
        def _(event: KeyPressEvent) -> None:
            """Insert newline on Ctrl+J (recommended Shift+Enter mapping in terminal)."""
            event.current_buffer.insert_text("\n")

        # Support Alt+Enter for newline without submission.
        @kb.add(Keys.Escape, Keys.Enter, eager=True)
        def _(event: KeyPressEvent) -> None:
            """Insert newline on Alt+Enter."""
            event.current_buffer.insert_text("\n")

        # Handle Ctrl+C - clean shutdown
        @kb.add("c-c")
        def _(event: KeyPressEvent) -> None:
            """Handle Ctrl+C - clean shutdown."""
            # Clear live area before exiting
            self._live_status_control.text = ""
            if self.app:
                self.app.invalidate()
            event.app.exit()

        # Handle Enter - submit prompt
        @kb.add(Keys.Enter)
        def _(event: KeyPressEvent) -> None:
            """Handle Enter - submit user input."""
            user_input = self._prompt_area.text.strip()
            if not user_input:
                return

            if user_input.lower() in ["exit", "quit", "/exit", "/quit"]:
                event.app.exit()
                return

            # Append to history, then clear the prompt area
            self._prompt_area.buffer.append_to_history()
            self._prompt_area.buffer.reset()
            # Print the input to terminal
            run_in_terminal(lambda: console.print(f"[dim]› {user_input}[/dim]\n"))

            # Start agent processing
            asyncio.create_task(self.agent.run(user_input))

        return kb

    async def run(self) -> None:
        """Interactive REPL loop for the console interface."""
        event_consumer_task = asyncio.create_task(self._event_stream_consumer())

        # Start the render loop
        self._start_render_loop()

        console.print(
            Panel(
                f"[bold cyan]╭─ OAI CODING AGENT ─╮[/bold cyan]\n\n"
                f"[dim]Current Directory:[/dim] [dim cyan]{self.agent.config.repo_path}[/dim cyan]\n"
                f"[dim]Model:[/dim] [dim cyan]{self.agent.config.model.value}[/dim cyan]\n"
                f"[dim]Mode:[/dim] [dim cyan]{self.agent.config.mode.value}[/dim cyan]",
                expand=False,
            )
        )

        kb = self._get_key_bindings()

        # Store prompt history under the XDG data directory
        history_dir = get_data_dir()
        history_dir.mkdir(parents=True, exist_ok=True)
        history_path = history_dir / "prompt_history"

        # Configure prompt area with history and styling
        self._prompt_area.buffer.history = FileHistory(str(history_path))

        # Create application with layout (live status always present)
        layout = HSplit([self._live_status_area, self._prompt_area])
        self.app = Application(
            layout=Layout(layout),
            key_bindings=kb,
            full_screen=False,
            style=Style.from_dict(
                {
                    "prompt": "ansicyan bold",
                    "auto-suggestion": "#888888",
                    "live-status": "ansigray",
                }
            ),
        )

        async with self.agent:
            try:
                logger.info("Starting prompt application...")
                await self.app.run_async()
            except (KeyboardInterrupt, EOFError):
                # Cancel any running agent task
                await self.agent.cancel()

            # Cancel the event consumer task when exiting
            event_consumer_task.cancel()
            self._stop_render_loop()
            try:
                await event_consumer_task
            except asyncio.CancelledError:
                pass
