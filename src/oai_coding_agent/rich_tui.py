import asyncio
import os
from pathlib import Path
from typing import Callable, Dict, List

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Heading, Markdown
from rich.panel import Panel

from .agent import AgentSession


# Classes to override the default Markdown renderer
class PlainHeading(Heading):
    """Left-aligned, no panel."""

    def __rich_console__(self, console, options):
        self.text.justify = "left"
        yield self.text


class PlainMarkdown(Markdown):
    elements = Markdown.elements.copy()
    elements["heading_open"] = PlainHeading


Markdown.elements["heading_open"] = PlainHeading

console = Console()

messages: List[dict] = []

slash_commands: Dict[str, Callable] = {}


def clear_terminal():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def render_message(msg: dict):
    """Render a single message."""
    role = msg.get("role")
    content = msg.get("content", "")
    if role == "user":
        console.print(f"[bold blue]You:[/bold blue] {content}\n")
    elif role == "assistant":
        console.print("[bold cyan]oai:[/bold cyan]", end=" ")
        md = Markdown(content, code_theme="nord", hyperlinks=True)
        console.print(md)
    elif role == "system":
        console.print(f"[dim yellow]System:[/dim yellow] [yellow]{content}[/yellow]\n")
    elif role == "thought":
        console.print(f"[italic dim]{content}[/italic dim]\n")
    elif role == "tool":
        console.print(f"[dim green]Tool: {content}[/dim green]\n")


def register_slash_commands():
    """Register all available slash commands."""
    global slash_commands
    slash_commands = {}

    def cmd_help(args=""):
        """Show help information for available commands."""
        help_text = "Available Commands:\n\n"
        for cmd, func in slash_commands.items():
            doc = func.__doc__ or "No description available"
            help_text += f"/{cmd} - {doc}\n"
        msg = {"role": "system", "content": help_text}
        messages.append(msg)
        render_message(msg)
        return True

    def cmd_clear(args=""):
        """Clear the chat history."""
        global messages
        messages = []
        msg = {"role": "system", "content": "Chat history has been cleared."}
        messages.append(msg)
        clear_terminal()
        render_message(msg)
        return True

    def cmd_exit(args=""):
        """Exit the application."""
        console.print("[yellow]Goodbye![/yellow]")
        return False

    def cmd_version(args=""):
        """Show version information."""
        msg = {
            "role": "system",
            "content": "CLI Chat Version: 0.1.0\nBuilt with Rich and prompt-toolkit",
        }
        messages.append(msg)
        render_message(msg)
        return True

    slash_commands["help"] = cmd_help
    slash_commands["clear"] = cmd_clear
    slash_commands["exit"] = cmd_exit
    slash_commands["quit"] = cmd_exit
    slash_commands["version"] = cmd_version


def handle_slash_command(text: str) -> bool:
    """Process slash commands and return whether to continue."""
    if not text.startswith("/"):
        return True
    parts = text[1:].split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    if cmd in slash_commands:
        try:
            return slash_commands[cmd](args)
        except Exception as e:
            msg = {"role": "system", "content": f"Error executing /{cmd}: {e}"}
            messages.append(msg)
            render_message(msg)
            return True
    else:
        msg = {
            "role": "system",
            "content": f"Unknown command: /{cmd}\nType /help to see available commands.",
        }
        messages.append(msg)
        render_message(msg)
        return True


async def main(repo_path: Path, model: str, openai_api_key: str):
    """Main application loop."""
    clear_terminal()

    register_slash_commands()

    # Display welcome panel with configuration info
    console.print(
        Panel(
            f"[bold cyan]╭─ OAI CODING AGENT ─╮[/bold cyan]\n\n"
            f"[dim]Current Directory:[/dim] [dim cyan]{repo_path}[/dim cyan]\n"
            f"[dim]Model:[/dim] [dim cyan]{model}[/dim cyan]",
            expand=False,
        )
    )

    # Set up prompt toolkit with custom key bindings
    kb = KeyBindings()

    @kb.add(Keys.Tab)
    def _(event):
        buffer = event.current_buffer
        suggestion = buffer.suggestion
        if suggestion:
            buffer.insert_text(suggestion.text)
        else:
            buffer.complete_next()

    # ------------------------------------------------------------------
    # Store history alongside logs/config in ~/.oai_coding_agent
    # ------------------------------------------------------------------
    history_path = Path.home() / ".oai_coding_agent" / "prompt_history"
    history_path.parent.mkdir(parents=True, exist_ok=True)

    prompt_session: PromptSession = PromptSession(
        history=FileHistory(str(history_path)),
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
        complete_while_typing=True,
        completer=WordCompleter([f"/{c}" for c in slash_commands]),
        complete_in_thread=True,
        key_bindings=kb,
        style=Style.from_dict(
            {"prompt": "ansicyan bold", "auto-suggestion": "#888888"}
        ),
        erase_when_done=True,
    )

    async with AgentSession(
        repo_path=repo_path, model=model, openai_api_key=openai_api_key
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
                    continue_loop = slash_commands["exit"]()
                    continue

                if user_input.startswith("/"):
                    continue_loop = handle_slash_command(user_input)
                    continue

                user_msg = {"role": "user", "content": user_input}
                messages.append(user_msg)
                console.print(f"[dim]› {user_input}[/dim]\n")

                ui_stream, result = await session_agent.run_step(user_input, prev_id)

                async for msg in ui_stream:
                    messages.append(msg)
                    render_message(msg)

                # Update prev_id for next iteration
                prev_id = result.last_response_id

            except (KeyboardInterrupt, EOFError):
                continue_loop = False
