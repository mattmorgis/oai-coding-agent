import asyncio
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.panel import Panel

from ..agent import AgentSession
from .state import UIState
from .rendering import console, clear_terminal, render_message
from .slash_commands import register_slash_commands, handle_slash_command
from .key_bindings import get_key_bindings


async def main(
    repo_path: Path,
    model: str,
    openai_api_key: str,
    github_personal_access_token: str,
    mode: str = "default",
) -> None:
    """Main REPL loop for the console interface."""
    state = UIState()
    clear_terminal()

    register_slash_commands(state)

    console.print(
        Panel(
            f"[bold cyan]╭─ OAI CODING AGENT ─╮[/bold cyan]\n\n"
            f"[dim]Current Directory:[/dim] [dim cyan]{repo_path}[/dim cyan]\n"
            f"[dim]Model:[/dim] [dim cyan]{model}[/dim cyan]\n"
            f"[dim]Mode:[/dim] [dim cyan]{mode}[/dim cyan]",
            expand=False,
        )
    )

    kb = get_key_bindings()

    # Store history alongside logs/config in ~/.oai_coding_agent
    history_path = Path.home() / ".oai_coding_agent" / "prompt_history"
    history_path.parent.mkdir(parents=True, exist_ok=True)

    prompt_session = PromptSession(
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

    async with AgentSession(
        repo_path=repo_path,
        model=model,
        openai_api_key=openai_api_key,
        github_personal_access_token=github_personal_access_token,
        mode=mode,
    ) as session_agent:
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

                user_msg = {"role": "user", "content": user_input}
                state.messages.append(user_msg)
                console.print(f"[dim]› {user_input}[/dim]\n")

                ui_stream, result = await session_agent.run_step(user_input, prev_id)
                async for msg in ui_stream:
                    state.messages.append(msg)
                    render_message(msg)

                prev_id = result.last_response_id

            except (KeyboardInterrupt, EOFError):
                continue_loop = False
