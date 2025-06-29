import asyncio
import logging
from dataclasses import dataclass
from itertools import cycle
from typing import Callable, Generator, List, Optional

from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import completion_is_selected, has_completions
from prompt_toolkit.formatted_text import HTML, FormattedText, to_formatted_text
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.styles import Style
from rich.panel import Panel

from oai_coding_agent.agent import AsyncAgentProtocol
from oai_coding_agent.console.rendering import console, render_event
from oai_coding_agent.runtime_config import get_data_dir


@dataclass(frozen=True)
class SlashCommand:
    """Definition of a slash command: name and description."""

    name: str
    description: str


class SlashCommandHandler:
    """Encapsulates slash-commands: completion, suggestion, handling and style settings."""

    style: Style = Style.from_dict(
        {
            "completion-menu": "noinherit",
            "completion-menu.completion": "noinherit",
            "completion-menu.scrollbar": "noinherit",
            "completion-menu.completion.current": "noinherit bold",
            "scrollbar": "noinherit",
            "scrollbar.background": "noinherit",
            "scrollbar.button": "noinherit",
            "bottom-toolbar": "noreverse",
        }
    )

    def __init__(self, printer: Callable[[str, str], None]) -> None:
        self._printer = printer
        self._commands: List[SlashCommand] = [
            SlashCommand(
                "/vim", "Toggle between vim and emacs mode (default is emacs)"
            ),
            SlashCommand("/clear", "Clear conversation history and free up context"),
            SlashCommand(
                "/cost", "Show the total cost and duration of the current session"
            ),
            SlashCommand(
                "/github-login",
                "Login to GitHub",
            ),
            SlashCommand(
                "/install-workflow",
                "Adds a workflow to the repo to use agent in GitHub Actions",
            ),
            SlashCommand("/help", "Show help and available commands"),
            SlashCommand("/exit (quit)", "Exit the REPL"),
        ]

    @property
    def completer(self) -> Completer:
        handler = self

        class _SlashCompleter(Completer):
            def get_completions(
                self, document: Document, complete_event: CompleteEvent
            ) -> Generator[Completion, None, None]:
                text = document.text
                if document.cursor_position_row != 0 or not text.startswith("/"):
                    return
                for cmd in handler._commands:
                    base = cmd.name.split()[0]
                    if base.lower().startswith(text.lower()):
                        display = f"{cmd.name:<20} {cmd.description}"
                        yield Completion(
                            base, start_position=-len(text), display=display
                        )

        return _SlashCompleter()

    @property
    def auto_suggest(self) -> AutoSuggest:
        handler = self

        class _SlashAutoSuggest(AutoSuggest):
            def get_suggestion(
                self, buffer: Buffer, document: Document
            ) -> Optional[Suggestion]:
                text = document.text
                if not text.startswith("/") or len(text) <= 1:
                    return None
                for cmd in handler._commands:
                    base = cmd.name.split()[0]
                    if (
                        base.lower().startswith(text.lower())
                        and base.lower() != text.lower()
                    ):
                        return Suggestion(base[len(text) :])
                return None

        return _SlashAutoSuggest()

    @staticmethod
    def on_completions_changed(buf: Buffer) -> None:
        state = buf.complete_state
        if state and state.complete_index is None:
            state.complete_index = 0

    def handle(self, user_input: str) -> bool:
        """Process a slash command; returns True if handled (only if valid command)."""
        text = user_input.strip()
        if not text.startswith("/"):
            return False
        # Extract base (first token) and check if it's a known slash command
        base = text.split()[0]
        valid_bases = [cmd.name.split()[0].lower() for cmd in self._commands]
        if base.lower() not in valid_bases:
            return False
        self._printer(f"Slash command: {user_input}\n", "yellow")
        return True


logger = logging.getLogger(__name__)


class Spinner:
    def __init__(self) -> None:
        self._frames = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
        self._cycle = cycle(self._frames)
        self._current_frame = next(self._cycle)

    def update(self) -> None:
        """Update spinner frame."""
        self._current_frame = next(self._cycle)

    @property
    def current_frame(self) -> str:
        return self._current_frame


class ReplConsole:
    """Console that runs interactive REPL mode."""

    agent: AsyncAgentProtocol
    prompt_session: Optional[PromptSession[str]]

    _render_task: Optional[asyncio.Task[None]]
    _should_stop_render: bool

    def __init__(self, agent: AsyncAgentProtocol) -> None:
        self.agent = agent

        # Create live status area (1 line, non-focusable; shows spinner "thinking..." or bullet "idle")
        self._live_status: FormattedText = to_formatted_text(HTML("idle"))

        self.prompt_session = None
        self._spinner = Spinner()
        self._render_task = None
        self._should_stop_render = False
        self._slash_handler = SlashCommandHandler(self._print_to_terminal)

    def prompt_fragments(self) -> FormattedText:
        """Return the complete prompt: status + prompt symbol."""
        if not self.agent.is_processing:
            return to_formatted_text("\n› ")

        # First line: cyan spinner + status, Second line: actual prompt
        formatted_text = HTML(
            f"<ansicyan>{self._spinner.current_frame} thinking...</ansicyan> "
            f"(<ansigray><b>ESC</b></ansigray> to interrupt)\n›"
        )
        return to_formatted_text(formatted_text)

    async def _render_loop(self) -> None:
        """Main render loop - updates live area based on agent state."""
        try:
            while not self._should_stop_render:
                if self.agent.is_processing:
                    # Update spinner and show live area
                    self._spinner.update()

                if self.prompt_session and self.prompt_session.app:
                    self.prompt_session.app.invalidate()

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
        def insert_or_accept(event: KeyPressEvent) -> None:
            buffer = event.current_buffer
            state = buffer.complete_state

            if not completion_is_selected():  # user never arrowed/tabbed
                state.complete_index = state.complete_index or 0  # type: ignore
            buffer.apply_completion(state.current_completion)  # type: ignore
            buffer.cancel_completion()
            buffer.validate_and_handle()

        @kb.add("tab", filter=has_completions)
        def accept_or_cycle(event: KeyPressEvent) -> None:
            buffer = event.current_buffer
            state = buffer.complete_state

            # If there is only one completion, treat Tab like "auto-complete"
            if len(state.completions) == 1:  # type: ignore
                state.complete_index = 0  # type: ignore
                buffer.apply_completion(state.current_completion)  # type: ignore
                buffer.cancel_completion()
            # If there are multiple completes, tab should cycle through
            else:
                buffer.complete_next()

        @kb.add("escape")
        async def _(event: KeyPressEvent) -> None:
            """Handle ESC - cancel current job."""
            await self.agent.cancel()
            await run_in_terminal(
                lambda: self._print_to_terminal(
                    "error: Agent cancelled by user", "bold red"
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

        return kb

    def _print_to_terminal(self, message: str, style: str = "") -> None:
        """Helper method to print messages to terminal with optional styling."""
        styled_message = f"[{style}]{message}[/{style}]" if style else message
        run_in_terminal(lambda: console.print(styled_message))

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

        self.prompt_session = PromptSession(
            message=self.prompt_fragments,
            history=FileHistory(str(history_path)),
            completer=self._slash_handler.completer,
            auto_suggest=self._slash_handler.auto_suggest,
            style=self._slash_handler.style,
            complete_while_typing=True,
            key_bindings=kb,
            erase_when_done=True,
        )
        if hasattr(self.prompt_session, "default_buffer"):
            buffer = self.prompt_session.default_buffer
            buffer.on_completions_changed += self._slash_handler.on_completions_changed

        async with self.agent:
            try:
                should_continue = True
                while should_continue:
                    logger.info("Prompting user...")
                    user_input = await self.prompt_session.prompt_async()
                    if not user_input.strip():
                        continue

                    if user_input.strip().lower() in ["exit", "quit", "/exit", "/quit"]:
                        should_continue = False
                        continue

                    if self._slash_handler.handle(user_input):
                        continue

                    self._print_to_terminal(f"› {user_input}\n", "dim")

                    await self.agent.run(user_input)

            except (KeyboardInterrupt, EOFError):
                # Cancel any running agent task
                await self.agent.cancel()
                should_continue = False

            # Cancel the event consumer task when exiting
            event_consumer_task.cancel()
            self._stop_render_loop()
            try:
                await event_consumer_task
            except asyncio.CancelledError:
                pass
