import asyncio
from pathlib import Path
from typing import Protocol

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.panel import Panel

from ..agent.agent import Agent
from ..runtime_config import RuntimeConfig
from .key_bindings import get_key_bindings
from .rendering import clear_terminal, console, render_message
from .slash_commands import handle_slash_command, register_slash_commands
from .state import UIState


class Console(Protocol):
    """Common interface for console interactions."""

    config: RuntimeConfig

    async def run(self) -> None:
        pass


class HeadlessConsole:
    """Console that runs headless (single prompt) mode."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config

    async def run(self) -> None:
        """
        Execute one prompt in async 'headless' mode and render streamed output.
        """
        if not self.config.prompt:
            raise ValueError("Prompt is required for headless mode")

        console.print(f"[bold cyan]Prompt:[/bold cyan] {self.config.prompt}")
        async with Agent(self.config) as agent:
            ui_stream, _ = await agent.run(self.config.prompt)
            async for msg in ui_stream:
                render_message(msg)


class ReplConsole:
    """Console that runs interactive REPL mode."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config

    async def run(self) -> None:
        """Interactive REPL loop for the console interface."""
        state = UIState()
        clear_terminal()

        register_slash_commands(state)

        console.print(
            Panel(
                f"[bold cyan]╭─ OAI CODING AGENT ─╮[/bold cyan]\n\n"
                f"[dim]Current Directory:[/dim] [dim cyan]{self.config.repo_path}[/dim cyan]\n"
                f"[dim]Model:[/dim] [dim cyan]{self.config.model.value}[/dim cyan]\n"
                f"[dim]Mode:[/dim] [dim cyan]{self.config.mode.value}[/dim cyan]",
                expand=False,
            )
        )

        kb = get_key_bindings()

        # Store history alongside logs/config in ~/.oai_coding_agent
        history_path = Path.home() / ".oai_coding_agent" / "prompt_history"
        history_path.parent.mkdir(parents=True, exist_ok=True)

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

        async with Agent(self.config) as agent:
            prev_id = None
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

                    ui_stream, result = await agent.run(user_input, prev_id)
                    async for msg in ui_stream:
                        render_message(msg)

                    prev_id = result.last_response_id

                except (KeyboardInterrupt, EOFError):
                    continue_loop = False


async def main(config: RuntimeConfig) -> None:
    """
    Unified entry point for both interactive REPL and headless modes.

    Args:
        config: Runtime configuration for the agent.
    """
    console: Console
    if config.prompt:
        console = HeadlessConsole(config)
    else:
        console = ReplConsole(config)

    await console.run()
