import asyncio
import logging
import random
from itertools import cycle
from typing import Callable, List, Optional

from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.filters import completion_is_selected, has_completions
from prompt_toolkit.formatted_text import FormattedText, to_formatted_text
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.shortcuts import PromptSession
from rich.panel import Panel

from oai_coding_agent.agent import AsyncAgentProtocol
from oai_coding_agent.agent.events import UsageEvent
from oai_coding_agent.console.rendering import console, render_event
from oai_coding_agent.console.slash_commands import SlashCommandHandler
from oai_coding_agent.console.token_animator import TokenAnimator
from oai_coding_agent.xdg import get_data_dir

logger = logging.getLogger(__name__)


class KeyBindingsHandler:
    """Encapsulates custom key bindings for the REPL (Enter, Tab, ESC, Ctrl+J, Alt+Enter)."""

    def __init__(
        self, agent: AsyncAgentProtocol, printer: Callable[[str, str], None]
    ) -> None:
        self.agent = agent
        self._printer = printer

    @property
    def bindings(self) -> KeyBindings:
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

        @kb.add("up")
        def up_or_previous(event: KeyPressEvent) -> None:
            """Handle up arrow - either navigate completions or history."""
            buffer = event.current_buffer
            if buffer.complete_state and buffer.complete_state.completions:
                buffer.complete_previous()
            else:
                buffer.history_backward()

        @kb.add("down")
        def down_or_next(event: KeyPressEvent) -> None:
            """Handle down arrow - either navigate completions or history."""
            buffer = event.current_buffer
            if buffer.complete_state and buffer.complete_state.completions:
                buffer.complete_next()
            else:
                buffer.history_forward()

        @kb.add("escape")
        async def _(event: KeyPressEvent) -> None:
            """Handle ESC - cancel current job if agent is processing."""
            if self.agent.is_processing:
                await self.agent.cancel()
                await run_in_terminal(
                    lambda: self._printer("error: Agent cancelled by user", "bold red")
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


class WordCycler:
    """Background word cycler: rotates through provided words every interval seconds.

    If no interval is provided, a random interval between 12 and 24 seconds is chosen.
    """

    def __init__(self, words: List[str], interval: Optional[float] = None) -> None:
        self._words = words
        if interval is None:
            interval = random.uniform(12.0, 24.0)

        self._cycle = cycle(self._words)
        self._current_word = next(self._cycle)
        self._interval = interval
        self._task: Optional[asyncio.Task[None]] = None

    @property
    def current_word(self) -> str:
        return self._current_word

    def start(self) -> None:
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._interval)
                self._current_word = next(self._cycle)
        except asyncio.CancelledError:
            pass


class Spinner:
    def __init__(self, interval: float = 0.1) -> None:
        self._frames = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
        self._cycle = cycle(self._frames)
        self._current_frame = next(self._cycle)
        self._interval = interval
        self._task: Optional[asyncio.Task[None]] = None

    def update(self) -> None:
        """(Deprecated) Update spinner frame."""
        self._current_frame = next(self._cycle)

    def start(self) -> None:
        """Start the spinner animation."""
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        """Stop the spinner animation."""
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run(self) -> None:
        """Advance spinner frames on a timer."""
        try:
            while True:
                self._current_frame = next(self._cycle)
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            pass

    @property
    def current_frame(self) -> str:
        return self._current_frame


class ReplConsole:
    """Console that runs interactive REPL mode."""

    agent: AsyncAgentProtocol
    prompt_session: Optional[PromptSession[str]]

    _render_task: Optional[asyncio.Task[None]]
    _should_stop_render: bool
    _usage_state: UsageEvent

    def __init__(self, agent: AsyncAgentProtocol) -> None:
        self.agent = agent

        self.prompt_session = None
        self._spinner = Spinner()
        self._render_task = None
        self._should_stop_render = False
        self._slash_handler = SlashCommandHandler(
            self._print_to_terminal, self.agent.config
        )
        self._kb_handler = KeyBindingsHandler(self.agent, self._print_to_terminal)
        self._word_cycler = WordCycler(
            [
                "processing",
                "analyzing",
                "reasoning",
                "planning",
                "evaluating",
                "considering",
                "working",
                "computing",
                "deciding",
                "pondering",
                "calculating",
                "strategizing",
                "formulating",
                "reflecting",
            ],
        )
        # Initialize cumulative usage state and token animator
        self._usage_state: UsageEvent = UsageEvent(0, 0, 0, 0, 0)

        self._token_animator = TokenAnimator(
            interval=0.1,
            animation_duration=1.0,
        )

    def prompt_fragments(self) -> FormattedText:
        """Return the complete prompt: status + prompt symbol."""
        if not self.agent.is_processing:
            return FormattedText([("ansicyan", "\n\n› ")])

        sp = self._spinner.current_frame
        wd = self._word_cycler.current_word
        ci = self._token_animator.current_input
        co = self._token_animator.current_output

        metrics = (
            f"[{TokenAnimator.format_count(ci)}↑/{TokenAnimator.format_count(co)}↓]"
        )
        spacer = " " * 28

        fragments = [
            ("", " "),
            ("ansicyan", sp),
            ("italic", f" {wd}"),
            ("", spacer),
            ("ansiyellow", metrics),
            ("", " "),
            ("dim", "    ("),
            ("dim bold", "esc "),
            ("dim", "to interrupt)\n\n"),
            ("ansicyan", "› "),
        ]
        return to_formatted_text(FormattedText(fragments))

    async def _render_loop(self) -> None:
        """Main render loop - updates live area based on agent state."""
        try:
            while not self._should_stop_render:
                # Spinner auto‑ticks in background; just invalidate UI

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
            if isinstance(agent_event, UsageEvent):
                # Update cumulative usage and animate tokens
                self._usage_state = self._usage_state + agent_event
                self._token_animator.update(self._usage_state)
                continue
            await run_in_terminal(lambda: render_event(agent_event))

    def _print_to_terminal(self, message: str, style: str = "") -> None:
        """Helper method to print messages to terminal with optional styling."""
        styled_message = f"[{style}]{message}[/{style}]" if style else message
        run_in_terminal(lambda: console.print(styled_message))

    async def run(self) -> None:
        """Interactive REPL loop for the console interface."""
        event_consumer_task = asyncio.create_task(self._event_stream_consumer())

        # Start spinner and render loop
        self._spinner.start()
        self._word_cycler.start()
        self._token_animator.start()
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

        kb = self._kb_handler.bindings

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

                    if await self._slash_handler.handle(user_input):
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
            self._spinner.stop()
            self._word_cycler.stop()
            self._token_animator.stop()
            try:
                await event_consumer_task
            except asyncio.CancelledError:
                pass
