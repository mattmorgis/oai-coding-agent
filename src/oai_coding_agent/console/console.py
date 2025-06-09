import asyncio
from typing import Protocol

from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout import Layout
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea
from rich.panel import Panel

from oai_coding_agent.agent import AgentProtocol
from oai_coding_agent.console.key_bindings import (
    get_bg_prompt_key_bindings,
    get_key_bindings,
)
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
            key_bindings=get_key_bindings(),
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

                    event_stream, result = await self.agent.run(user_input)

                    # Consume the event stream in its own task (so it can be cancelled).
                    async def _consume_stream() -> None:
                        async for event in event_stream:
                            ui_msg = map_event_to_ui_message(event)
                            if ui_msg:
                                render_message(ui_msg)

                    # Create a fresh mini application each time
                    bg_prompt_app: Application[None] = Application(
                        layout=Layout(TextArea("", focusable=False)),
                        key_bindings=get_bg_prompt_key_bindings(state),
                        full_screen=False,
                        mouse_support=False,
                        erase_when_done=True,
                        output=None,
                    )

                    # Mini application that keeps key bindings alive during streaming
                    async def _run_mini_app() -> None:
                        await bg_prompt_app.run_async()

                    # Schedule both tasks.
                    stream_llm_task = asyncio.create_task(_consume_stream())
                    bg_prompt_task = asyncio.create_task(_run_mini_app())

                    state.set_running_task(
                        stream_llm_task,
                        result,
                        getattr(self.agent, "_previous_response_id", None),
                    )

                    try:
                        # Wait until either the stream finishes or the user interrupts.
                        done, pending = await asyncio.wait(
                            {stream_llm_task, bg_prompt_task},
                            return_when=asyncio.FIRST_COMPLETED,
                        )

                        # Clean up the remaining tasks
                        for task in pending:
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass

                        # Ensure mini application is properly exited
                        if not bg_prompt_task.done():
                            bg_prompt_app.exit()
                    finally:
                        state.cancel_current_task()
                        if state.interrupted:
                            self.agent._previous_response_id = (
                                state.last_completed_response_id
                            )

                except (KeyboardInterrupt, EOFError):
                    continue_loop = False
