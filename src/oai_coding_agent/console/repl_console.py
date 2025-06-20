import asyncio
import logging

from prompt_toolkit import PromptSession
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from rich.panel import Panel

from oai_coding_agent.agent import AgentProtocol
from oai_coding_agent.console.rendering import clear_terminal, console, render_message
from oai_coding_agent.console.ui_event_mapper import UIMessage, map_event_to_ui_message
from oai_coding_agent.runtime_config import get_data_dir

logger = logging.getLogger(__name__)


class ReplConsole:
    """Console that runs interactive REPL mode."""

    agent: AgentProtocol

    _prompt_session: PromptSession[str]

    def __init__(self, agent: AgentProtocol) -> None:
        self.agent = agent

    async def _event_stream_consumer(self) -> None:
        while True:
            agent_event = await self.agent.events.get()
            await run_in_terminal(
                lambda: render_message(map_event_to_ui_message(agent_event))
            )

    def _get_key_bindings(self) -> KeyBindings:
        """Return the custom KeyBindings (e.g. Tab behaviour)."""
        kb = KeyBindings()

        @kb.add(Keys.Tab)
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
                lambda: render_message(
                    UIMessage(role="error", content="Agent cancelled by user")
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
        asyncio.create_task(self._event_stream_consumer())

        clear_terminal()

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

        prompt_session: PromptSession[str] = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
            complete_while_typing=True,
            complete_in_thread=True,
            key_bindings=kb,
            style=Style.from_dict(
                {"prompt": "ansicyan bold", "auto-suggestion": "#888888"}
            ),
            erase_when_done=True,
        )

        # Don’t start the agent until the first prompt is actually on screen.
        logger.debug(
            "ReplConsole: creating start_init_event and registering pre_run callback"
        )
        start_event = asyncio.Event()
        self.agent._start_init_event = start_event
        prompt_session.app.pre_run_callables.append(lambda: start_event.set())

        # Debug: show when entering agent context
        logger.debug("ReplConsole: entering async with self.agent")
        async with self.agent:
            continue_loop = True
            while continue_loop:
                try:
                    user_input = await prompt_session.prompt_async("› ")
                    if not user_input.strip():
                        continue

                    if user_input.strip().lower() in ["exit", "quit", "/exit", "/quit"]:
                        continue_loop = False
                        continue

                    console.print(f"[dim]› {user_input}[/dim]\n")

                    await self.agent.run(user_input)

                except (KeyboardInterrupt, EOFError):
                    continue_loop = False
