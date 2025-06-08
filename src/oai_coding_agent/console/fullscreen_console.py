"""
Full-screen console implementation using prompt_toolkit Application.

This provides a VS Code-friendly interface with:
- Live streaming from multiple engines
- Persistent input line at the bottom
- Token counter in the footer
- History popup on demand
"""

import asyncio
import io
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import AnyFormattedText, FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    Container,
    Float,
    FloatContainer,
    HSplit,
    Layout,
    VSplit,
    Window,
    WindowAlign,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame
from rich.console import Console as RichConsole
from rich.panel import Panel
from rich.spinner import Spinner

from oai_coding_agent.agent import AgentProtocol
from oai_coding_agent.agent.events import (
    MessageOutputEvent,
    ReasoningEvent,
    ToolCallEvent,
)
from oai_coding_agent.console.slash_commands import (
    handle_slash_command,
    register_slash_commands,
)
from oai_coding_agent.console.state import UIState
from oai_coding_agent.console.ui_event_mapper import map_event_to_ui_message
from oai_coding_agent.runtime_config import get_data_dir


@dataclass
class EngineState:
    """State for a single streaming engine."""

    name: str
    tokens: int = 0
    is_streaming: bool = False
    content: str = ""
    color: str = "cyan"
    start_line: int = 0  # Line number in scrollback where this engine's output starts


@dataclass
class FullscreenUIState:
    """Extended UI state for fullscreen mode."""

    engines: Dict[str, EngineState] = field(default_factory=dict)
    history_popup_visible: bool = False
    selected_history_index: int = 0
    response_history: List[Dict[str, Any]] = field(default_factory=list)
    interrupt_visible: bool = False
    interrupt_hide_time: Optional[float] = None
    token_counter: int = 0  # For demo purposes


class FullscreenConsole:
    """Full-screen console with prompt_toolkit Application."""

    def __init__(self, agent: AgentProtocol) -> None:
        self.agent = agent
        self.ui_state = UIState()
        self.fs_state = FullscreenUIState()
        self.app: Optional[Application[Any]] = None

        # Buffers
        self.input_buffer = Buffer(multiline=False)
        self.scrollback_text = ""  # Store scrollback as string
        self.scrollback_buffer = Buffer(read_only=True)

        # Rich console for rendering into scrollback
        # We'll capture output to update the scrollback buffer
        self.rich_console: Optional[RichConsole] = None

        # Track active stream task
        self.stream_task: Optional[asyncio.Task[Any]] = None

        # Key bindings
        self.kb = self._create_key_bindings()

        # History
        history_dir = get_data_dir()
        history_dir.mkdir(parents=True, exist_ok=True)
        self.history_path = history_dir / "prompt_history"
        self.response_history_path = history_dir / "response_history.jsonl"

    def _create_key_bindings(self) -> KeyBindings:
        """Create key bindings for the application."""
        kb = KeyBindings()

        @kb.add("c-c")
        def _(event) -> None:
            """Handle Ctrl+C."""
            if self.stream_task and not self.stream_task.done():
                # If streaming, interrupt
                self.stream_task.cancel()
                if hasattr(self.agent, "result"):
                    self.agent.result.cancel()
            else:
                # If idle, exit
                event.app.exit()

        @kb.add("enter")
        def _(event) -> None:
            """Handle Enter - submit input."""
            text = self.input_buffer.text.strip()
            if text:
                # Add to scrollback with better formatting
                user_input = f"[bold green]›[/bold green] {text}"
                self._append_to_scrollback(user_input)
                # Clear input
                self.input_buffer.reset()
                # Process command
                asyncio.create_task(self._process_input(text))

        @kb.add("up")
        def _(event) -> None:
            """Navigate history popup if visible."""
            if self.fs_state.history_popup_visible:
                if self.fs_state.selected_history_index > 0:
                    self.fs_state.selected_history_index -= 1
                    event.app.invalidate()

        @kb.add("down")
        def _(event) -> None:
            """Navigate history popup if visible."""
            if self.fs_state.history_popup_visible:
                if (
                    self.fs_state.selected_history_index
                    < len(self.fs_state.response_history) - 1
                ):
                    self.fs_state.selected_history_index += 1
                    event.app.invalidate()

        @kb.add("escape")
        def _(event) -> None:
            """Close popups."""
            if self.fs_state.history_popup_visible:
                self.fs_state.history_popup_visible = False
                event.app.invalidate()

        return kb

    def _append_to_scrollback(self, text: str) -> None:
        """Append text to the scrollback buffer."""
        if self.scrollback_text and not self.scrollback_text.endswith("\n"):
            self.scrollback_text += "\n"
        self.scrollback_text += text
        # Ensure proper line ending
        if not self.scrollback_text.endswith("\n"):
            self.scrollback_text += "\n"

        # Update the buffer by creating a new document
        self.scrollback_buffer.set_document(
            Document(self.scrollback_text), bypass_readonly=True
        )
        # Scroll to bottom
        self.scrollback_buffer.cursor_position = len(self.scrollback_text)
        if self.app:
            self.app.invalidate()

    def _render_rich_to_scrollback(self, renderable: Any) -> str:
        """Render a Rich object to ANSI text and append to scrollback."""
        # Create a string buffer to capture output
        buf = io.StringIO()
        # Create a console that writes to our buffer
        console = RichConsole(
            file=buf, width=self._get_terminal_width(), legacy_windows=False
        )
        console.print(renderable)
        # Get the ANSI text
        ansi_text = buf.getvalue()
        # Append to scrollback
        self._append_to_scrollback(ansi_text.rstrip())
        return ansi_text

    def _get_terminal_width(self) -> int:
        """Get the current terminal width."""
        if self.app and self.app.output:
            return self.app.output.get_size().columns
        return 80  # Default fallback

    def _update_engine_output(self, engine_id: str, content: str) -> None:
        """Update the output for a specific engine in the scrollback."""
        if engine_id not in self.fs_state.engines:
            return

        engine = self.fs_state.engines[engine_id]
        engine.content = content

        # Create the updated panel
        spinner = Spinner("dots", style=engine.color) if engine.is_streaming else ""
        title = f"{engine.name} {spinner}" if engine.is_streaming else engine.name
        panel = Panel(
            content,
            title=title,
            title_align="left",
            border_style=engine.color,
            expand=False,
            padding=(0, 1),
        )

        # Render to ANSI
        buf = io.StringIO()
        console = RichConsole(
            file=buf, width=self._get_terminal_width(), legacy_windows=False
        )
        console.print(panel)
        ansi_text = buf.getvalue()

        # Update the scrollback buffer in place
        lines = self.scrollback_text.split("\n")

        # Find where this engine's output starts
        if engine.start_line < len(lines):
            # Count how many lines the old output takes
            old_line_count = 0
            i = engine.start_line
            # Simple heuristic: count until we hit another engine marker or end
            while i < len(lines) and not lines[i].strip().startswith("›"):
                old_line_count += 1
                i += 1

            # Replace the old lines with new rendered output
            new_lines = ansi_text.rstrip().split("\n")
            lines[engine.start_line : engine.start_line + old_line_count] = new_lines

            # Update the buffer
            self.scrollback_text = "\n".join(lines)
            self.scrollback_buffer.set_document(
                Document(self.scrollback_text), bypass_readonly=True
            )
            self.scrollback_buffer.cursor_position = len(self.scrollback_text)

            if self.app:
                self.app.invalidate()

    def _get_footer_text(self) -> AnyFormattedText:
        """Generate footer text with token counts and status."""
        parts = []

        # Show token counts for active engines
        for engine_name, engine in self.fs_state.engines.items():
            if engine.is_streaming:
                parts.append(
                    (f"fg:{engine.color}", f"{engine_name}: {engine.tokens} tokens ")
                )

        # Show total tokens if available
        if self.fs_state.engines:
            total_tokens = sum(e.tokens for e in self.fs_state.engines.values())
            if total_tokens > 0:
                parts.append(("fg:white", f"total: {total_tokens} tokens "))

        # Show interrupt hint if streaming
        if any(e.is_streaming for e in self.fs_state.engines.values()):
            parts.append(("fg:yellow", "⠋ thinking... "))
            parts.append(("fg:gray", "Ctrl-C to interrupt"))
        else:
            # Show helpful hints when idle
            parts.append(("fg:gray", "Type your message or /help for commands"))

        # Show interrupt indicator temporarily
        if self.fs_state.interrupt_visible:
            if (
                self.fs_state.interrupt_hide_time
                and asyncio.get_event_loop().time() > self.fs_state.interrupt_hide_time
            ):
                self.fs_state.interrupt_visible = False
            else:
                parts = [
                    ("bold fg:red", "⏹ Interrupted "),
                    ("fg:red", "- conversation restored"),
                ]

        return FormattedText(parts)

    def _create_layout(self) -> Layout:
        """Create the application layout."""
        # Scrollback window
        scrollback_window = Window(
            BufferControl(self.scrollback_buffer),
            wrap_lines=True,
        )

        # Footer
        footer = Window(
            FormattedTextControl(self._get_footer_text),
            height=1,
            align=WindowAlign.LEFT,
            style="reverse",
        )

        # Input window with prompt
        input_window = Window(
            BufferControl(
                self.input_buffer,
                include_default_input_processors=True,
            ),
            height=1,
        )

        # Main layout
        root = HSplit(
            [
                scrollback_window,
                footer,
                VSplit(
                    [
                        Window(
                            FormattedTextControl([("bold fg:green", "› ")]), width=2
                        ),
                        input_window,
                    ]
                ),
            ]
        )

        # History popup (conditional)
        if self.fs_state.history_popup_visible:
            history_content = self._create_history_popup()
            container = FloatContainer(
                root,
                floats=[
                    Float(
                        content=history_content,
                        attach_to_window=input_window,
                        top=0,
                        bottom=0,
                    )
                ],
            )
        else:
            container = root

        return Layout(container, focused_element=input_window)

    def _create_history_popup(self) -> Container:
        """Create the history selection popup."""
        # For now, just a placeholder
        lines = []
        for i, item in enumerate(self.fs_state.response_history[-10:]):
            prefix = "▶ " if i == self.fs_state.selected_history_index else "  "
            lines.append(
                f"{prefix}{item.get('summary', 'Response')} - {item.get('created_at', '')}"
            )

        text = "\n".join(lines) if lines else "No history available"

        return Frame(
            Window(
                FormattedTextControl(text),
                height=Dimension(min=3, max=10),
            ),
            title="History",
        )

    async def _process_input(self, text: str) -> None:
        """Process user input."""
        # Handle slash commands
        if text.startswith("/"):
            if text == "/history":
                self.fs_state.history_popup_visible = True
                self.app.invalidate()
            elif text in ["/exit", "/quit"]:
                self.app.exit()
            else:
                # Use existing slash command handler
                continue_loop = handle_slash_command(self.ui_state, text)
                if not continue_loop:
                    self.app.exit()
            return

        # Run the agent
        try:
            # Snapshot the last completed response ID so we can restore on cancel
            last_completed_id = getattr(self.agent, "_previous_response_id", None)

            # Create engine state for this response
            engine_id = "assistant"
            engine = EngineState(
                name="Assistant",
                color="cyan",
                is_streaming=True,
                start_line=len(self.scrollback_text.split("\n")) - 1,
            )
            self.fs_state.engines[engine_id] = engine

            # Add spacing before response
            self._append_to_scrollback("\n")

            # Show thinking indicator
            thinking_panel = Panel(
                "[dim]⋯ thinking ⋯[/dim]",
                title="Assistant",
                title_align="left",
                border_style="cyan",
                expand=False,
                padding=(0, 1),
            )
            self._render_rich_to_scrollback(thinking_panel)

            # Track the line for replacement
            engine.start_line = len(self.scrollback_text.split("\n")) - 5

            # Get the event stream
            event_stream, result = await self.agent.run(text)

            # Consume the event stream
            async def _consume_stream() -> None:
                message_content = ""
                async for event in event_stream:
                    ui_msg = map_event_to_ui_message(event)
                    if ui_msg:
                        # Handle different event types
                        if isinstance(event, MessageOutputEvent):
                            # Accumulate message content
                            message_content = event.text
                            engine.content = message_content
                            engine.tokens = len(
                                message_content.split()
                            )  # Simple token estimate
                            self._update_engine_output(engine_id, message_content)
                        elif isinstance(event, ToolCallEvent):
                            # Add tool call info to content
                            tool_info = f"\n\n[dim]Tool: {event.tool_name}[/dim]"
                            self._update_engine_output(
                                engine_id, engine.content + tool_info
                            )
                        elif isinstance(event, ReasoningEvent):
                            # Optionally show reasoning
                            pass

            self.stream_task = asyncio.create_task(_consume_stream())

            try:
                await self.stream_task
                # Mark as completed
                engine.is_streaming = False
                self._update_engine_output(engine_id, engine.content)

                # Save to history
                self._save_response_to_history(
                    {
                        "id": str(datetime.now().timestamp()),
                        "summary": text[:50] + "..." if len(text) > 50 else text,
                        "created_at": datetime.now().isoformat(),
                        "content": engine.content,
                    }
                )
            except asyncio.CancelledError:
                # Interrupted
                self.fs_state.interrupt_visible = True
                self.fs_state.interrupt_hide_time = (
                    asyncio.get_event_loop().time() + 2.0
                )
                # Restore the last completed response id
                if hasattr(self.agent, "_previous_response_id"):
                    self.agent._previous_response_id = last_completed_id
                engine.is_streaming = False
                interrupt_panel = Panel(
                    engine.content + "\n\n[red bold]⏹ Interrupted[/red bold]",
                    title="Assistant",
                    title_align="left",
                    border_style="red",
                    expand=False,
                    padding=(0, 1),
                )
                self._render_rich_to_scrollback(interrupt_panel)

        except Exception as e:
            error_panel = Panel(
                f"[red bold]Error: {e}[/red bold]",
                title="Error",
                title_align="left",
                border_style="red",
                expand=False,
                padding=(0, 1),
            )
            self._render_rich_to_scrollback(error_panel)
        finally:
            # Clean up
            if engine_id in self.fs_state.engines:
                del self.fs_state.engines[engine_id]
            self.app.invalidate()

    def _save_response_to_history(self, response: Dict[str, Any]) -> None:
        """Save a response to the history file."""
        try:
            with open(self.response_history_path, "a") as f:
                f.write(json.dumps(response) + "\n")
            self.fs_state.response_history.append(response)
            # Keep only last 5000 entries in memory
            if len(self.fs_state.response_history) > 5000:
                self.fs_state.response_history = self.fs_state.response_history[-5000:]
        except Exception:
            pass  # Silently ignore history save errors

    def _load_response_history(self) -> None:
        """Load response history from file."""
        if self.response_history_path.exists():
            try:
                with open(self.response_history_path) as f:
                    for line in f:
                        if line.strip():
                            self.fs_state.response_history.append(json.loads(line))
                # Keep only last 5000 entries
                if len(self.fs_state.response_history) > 5000:
                    self.fs_state.response_history = self.fs_state.response_history[
                        -5000:
                    ]
            except Exception:
                pass  # Silently ignore history load errors

    async def _update_loop(self) -> None:
        """Background loop for updating UI."""
        while True:
            await asyncio.sleep(0.1)
            # Update any time-based UI elements
            if self.fs_state.interrupt_visible and self.fs_state.interrupt_hide_time:
                if asyncio.get_event_loop().time() > self.fs_state.interrupt_hide_time:
                    self.fs_state.interrupt_visible = False
                    self.app.invalidate()

    async def run(self) -> None:
        """Run the full-screen application."""
        # Register slash commands
        register_slash_commands(self.ui_state)

        # Load response history
        self._load_response_history()

        # Initial welcome message using Rich
        welcome_panel = Panel(
            f"[bold cyan]╭─ OAI CODING AGENT ─╮[/bold cyan]\n\n"
            f"[dim]Current Directory:[/dim] [dim cyan]{self.agent.config.repo_path}[/dim cyan]\n"
            f"[dim]Model:[/dim] [dim cyan]{self.agent.config.model.value}[/dim cyan]\n"
            f"[dim]Mode:[/dim] [dim cyan]{self.agent.config.mode.value}[/dim cyan]",
            expand=False,
            padding=(1, 1),
        )
        self._render_rich_to_scrollback(welcome_panel)

        # Create application
        self.app = Application(
            layout=self._create_layout(),
            key_bindings=self.kb,
            full_screen=True,
            style=Style.from_dict(
                {
                    "": "#ffffff",
                    "reverse": "reverse",
                }
            ),
            refresh_interval=0.1,  # 10 FPS max
            mouse_support=False,  # Disable mouse support for simplicity
        )

        # Run update loop in background
        update_task = asyncio.create_task(self._update_loop())

        try:
            async with self.agent:
                await self.app.run_async()
        finally:
            update_task.cancel()
            try:
                await update_task
            except asyncio.CancelledError:
                pass
