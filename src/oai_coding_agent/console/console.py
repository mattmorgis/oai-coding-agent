import asyncio
import signal
from contextlib import suppress
from typing import Protocol

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.panel import Panel

from oai_coding_agent.agent import AgentProtocol
from oai_coding_agent.console.key_bindings import get_key_bindings
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


class ReplConsole:
    """Console that runs interactive REPL mode."""

    def __init__(self, agent: AgentProtocol) -> None:
        self.agent = agent

    async def run(self) -> None:
        """Interactive REPL loop for the console interface."""
        state = UIState()
        clear_terminal()

        register_slash_commands(state)

        console.print(
            Panel(
                f"[bold cyan]╭─ OAI CODING AGENT ─╮[/bold cyan]\n\n"
                f"[dim]Current Directory:[/dim] [dim cyan]{self.agent.config.repo_path}[/dim cyan]\n"
                f"[dim]Model:[/dim] [dim cyan]{self.agent.config.model.value}[/dim cyan]\n"
                f"[dim]Mode:[/dim] [dim cyan]{self.agent.config.mode.value}[/dim cyan]",
                expand=False,
            )
        )

        kb = get_key_bindings()

        # Store prompt history under the XDG data directory
        history_dir = get_data_dir()
        history_dir.mkdir(parents=True, exist_ok=True)
        history_path = history_dir / "prompt_history"

        prompt_session: PromptSession[str] = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
            complete_while_typing=True,
            completer=WordCompleter([f"/{c}" for c in state.slash_commands]),
            complete_in_thread=True,
            key_bindings=kb,
            style=Style.from_dict(
                {"prompt": "ansicyan bold", "auto-suggestion": "#888888"}
            ),
            erase_when_done=True,
        )

        async with self.agent:
            continue_loop = True
            while continue_loop:
                try:
                    user_input = await asyncio.to_thread(
                        lambda: prompt_session.prompt("› ")
                    )
                    if not user_input.strip():
                        continue

                    if user_input.strip().lower() in ["exit", "quit", "/exit", "/quit"]:
                        continue_loop = state.slash_commands["exit"]("")
                        continue

                    if user_input.startswith("/"):
                        continue_loop = handle_slash_command(state, user_input)
                        continue

                    console.print(f"[dim]› {user_input}[/dim]\n")

                    # Snapshot the last completed response ID so we can restore on cancel
                    last_completed_id = getattr(
                        self.agent, "_previous_response_id", None
                    )

                    event_stream, result = await self.agent.run(user_input)

                    # Consume the event stream in its own task so we can cancel it on Ctrl+C
                    async def _consume_stream() -> None:
                        async for event in event_stream:
                            ui_msg = map_event_to_ui_message(event)
                            if ui_msg:
                                render_message(ui_msg)

                    stream_task = asyncio.create_task(_consume_stream())

                    interrupted = False  # Use a flag to track if interruption happened
                    with suppress(NotImplementedError):

                        def _on_sigint() -> None:
                            nonlocal interrupted
                            interrupted = True
                            stream_task.cancel()
                            result.cancel()
                            console.print("[red]\n⏹ Interrupted[/red]\n")

                        loop = asyncio.get_running_loop()
                        loop.add_signal_handler(signal.SIGINT, _on_sigint)

                    try:
                        await stream_task
                    except asyncio.CancelledError:
                        # Stream was already handled in _sigint_handler
                        pass
                    finally:
                        # Remove our temporary SIGINT handler so default behaviour is restored
                        with suppress(NotImplementedError):
                            loop.remove_signal_handler(signal.SIGINT)

                        # If interrupted, restore the last completed response id so the next
                        # turn stitches onto the correct conversation thread.
                        if interrupted:
                            if hasattr(self.agent, "_previous_response_id"):
                                self.agent._previous_response_id = last_completed_id

                except (KeyboardInterrupt, EOFError):
                    continue_loop = False
