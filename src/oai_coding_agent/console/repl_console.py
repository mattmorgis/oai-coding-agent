import asyncio
import logging
from typing import Generator, Optional

from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import has_completions
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

# --- Slash-command autocomplete (inline) ---
commands = [
    ("/add-dir", "Add a new working directory"),
    ("/bug", "Submit feedback about Claude Code"),
    ("/clear", "Clear conversation history and free up context"),
    (
        "/compact",
        "Clear conversation history but keep a summary in context. Optional: /compact [instructions for summarization]",
    ),
    ("/config (theme)", "Open config panel"),
    ("/cost", "Show the total cost and duration of the current session"),
    ("/doctor", "Checks the health of your Claude Code installation"),
    ("/exit (quit)", "Exit the REPL"),
    ("/help", "Show help and available commands"),
    ("/ide", "Manage IDE integrations and show status"),
]


class SlashCompleter(Completer):
    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Generator[Completion, None, None]:
        text = document.text

        # Only complete if we're on the first line and text starts with /
        if text.startswith("/"):
            for cmd, desc in commands:
                base_cmd = cmd.split()[0]
                if base_cmd.lower().startswith(text.lower()):
                    display = f"{cmd:<20} {desc}"
                    yield Completion(
                        base_cmd, start_position=-len(text), display=display
                    )


class SlashAutoSuggest(AutoSuggest):
    """Auto-suggest for slash commands."""

    def get_suggestion(
        self, buffer: Buffer, document: Document
    ) -> Optional[Suggestion]:
        text = document.text

        # Only suggest if we're on first line and text starts with / and has length > 1
        if text.startswith("/") and len(text) > 1:
            for cmd, desc in commands:
                base_cmd = cmd.split()[0]
                if (
                    base_cmd.lower().startswith(text.lower())
                    and base_cmd.lower() != text.lower()
                ):
                    return Suggestion(base_cmd[len(text) :])

        return None


# Minimal style for the slash menu
style = Style.from_dict(
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


def on_completions_changed(buf: Buffer) -> None:
    state = buf.complete_state
    if state and state.complete_index is None:
        state.complete_index = 0


# --- End slash-command autocomplete ---

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
        def _(event: KeyPressEvent) -> None:
            buffer = event.current_buffer
            suggestion = buffer.suggestion
            if suggestion:
                buffer.insert_text(suggestion.text)
            else:
                buffer.complete_next()

        @kb.add("tab", filter=has_completions)
        def _(event: KeyPressEvent) -> None:
            buf = event.current_buffer
            state = buf.complete_state
            assert state is not None
            if len(state.completions) == 1:
                if state.current_completion is None:
                    state.complete_index = 0
                assert state.current_completion is not None
                buf.apply_completion(state.current_completion)
                buf.cancel_completion()
            else:
                buf.complete_next()

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

        self.prompt_session = PromptSession(
            message=self.prompt_fragments,
            history=FileHistory(str(history_path)),
            completer=SlashCompleter(),
            auto_suggest=SlashAutoSuggest(),
            style=style,
            enable_history_search=True,
            complete_while_typing=True,
            key_bindings=kb,
            erase_when_done=True,
        )
        buf = self.prompt_session.default_buffer
        buf.on_completions_changed += on_completions_changed

        async with self.agent:
            try:
                continue_loop = True
                while continue_loop:
                    logger.info("Prompting user...")
                    user_input = await self.prompt_session.prompt_async()
                    if not user_input.strip():
                        continue

                    if user_input.strip().lower() in ["exit", "quit", "/exit", "/quit"]:
                        continue_loop = False
                        continue

                    run_in_terminal(
                        lambda: console.print(f"[dim]› {user_input}[/dim]\n")
                    )

                    await self.agent.run(user_input)

            except (KeyboardInterrupt, EOFError):
                # Cancel any running agent task
                await self.agent.cancel()
                continue_loop = False

            # Cancel the event consumer task when exiting
            event_consumer_task.cancel()
            self._stop_render_loop()
            try:
                await event_consumer_task
            except asyncio.CancelledError:
                pass
