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
thinking_active = False

slash_commands: Dict[str, Callable] = {}


def clear_terminal():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def render_messages():
    """Render all messages in the chat history."""
    clear_terminal()
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            console.print(f"[bold blue]You:[/bold blue] {content}\n")
        elif role == "assistant":
            console.print("[bold green]Assistant:[/bold green]")
            md = Markdown(content, code_theme="nord", hyperlinks=True)
            console.print(md)
            console.print()
        elif role == "thinking":
            console.print(f"[yellow]{content}[/yellow]\n")
        elif role == "system":
            console.print(
                f"[dim yellow]System:[/dim yellow] [yellow]{content}[/yellow]\n"
            )


async def animate_thinking():
    """Animate the thinking indicator."""
    global thinking_active
    states = ["🤔 Thinking.", "🤔 Thinking..", "🤔 Thinking..."]
    idx = 0
    while thinking_active:
        for i, m in enumerate(messages):
            if m.get("role") == "thinking":
                messages[i]["content"] = states[idx]
                break
        idx = (idx + 1) % len(states)
        render_messages()
        await asyncio.sleep(0.5)


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
        messages.append({"role": "system", "content": help_text})
        return True

    def cmd_clear(args=""):
        """Clear the chat history."""
        global messages
        messages = []
        messages.append({"role": "system", "content": "Chat history has been cleared."})
        return True

    def cmd_exit(args=""):
        """Exit the application."""
        console.print("[yellow]Goodbye![/yellow]")
        return False

    def cmd_version(args=""):
        """Show version information."""
        messages.append(
            {
                "role": "system",
                "content": "CLI Chat Version: 0.1.0\nBuilt with Rich and prompt-toolkit",
            }
        )
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
            messages.append(
                {"role": "system", "content": f"Error executing /{cmd}: {e}"}
            )
            return True
    else:
        messages.append(
            {
                "role": "system",
                "content": f"Unknown command: /{cmd}\nType /help to see available commands.",
            }
        )
        return True


async def main(repo_path: Path, model: str, openai_api_key: str):
    """Main application loop."""
    global thinking_active

    register_slash_commands()

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

    history_file = os.path.expanduser("~/.ai_chat_history")
    prompt_session: PromptSession = PromptSession(
        history=FileHistory(history_file),
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
        complete_while_typing=True,
        completer=WordCompleter([f"/{c}" for c in slash_commands]),
        complete_in_thread=True,
        key_bindings=kb,
        style=Style.from_dict(
            {"prompt": "ansicyan bold", "auto-suggestion": "#888888"}
        ),
    )

    # Welcome message
    messages.append(
        {
            "role": "assistant",
            "content": "Hello! I'm your AI coding assistant. How can I help you today?\n\nType `/help` to see available commands.",
        }
    )
    render_messages()

    async with AgentSession(
        repo_path=repo_path, model=model, openai_api_key=openai_api_key
    ) as session_agent:
        prev_id = None
        continue_loop = True
        while continue_loop:
            try:
                console.print()
                user_input = await asyncio.to_thread(
                    lambda: prompt_session.prompt("› ")
                )

                if not user_input.strip():
                    continue

                if user_input.strip().lower() in ["exit", "quit", "/exit", "/quit"]:
                    continue_loop = slash_commands["exit"]()
                    continue

                console.print(Panel(user_input, border_style="cyan", expand=False))

                if user_input.startswith("/"):
                    continue_loop = handle_slash_command(user_input)
                    if continue_loop:
                        render_messages()
                    continue

                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "thinking", "content": "🤔 Thinking..."})
                thinking_active = True
                thinking_task = asyncio.create_task(animate_thinking())

                events, prev_id = await session_agent.run_step(user_input, prev_id)

                async for event in events:
                    thinking_active = False
                    evt_type = getattr(event, "type", None)
                    evt_name = getattr(event, "name", None)

                    # Handle tool calls
                    if (
                        evt_type == "run_item_stream_event"
                        and evt_name == "tool_called"
                    ):
                        messages.append(
                            {
                                "role": "system",
                                "content": f"-- Tool {event.item.raw_item.name} was called with args: {event.item.raw_item.arguments}",
                            }
                        )
                    # Handle reasoning items
                    elif evt_name == "reasoning_item_created":
                        summary = event.item.raw_item.summary
                        if summary:
                            text = summary[0].text
                            messages.append(
                                {
                                    "role": "system",
                                    "content": f"-- Reasoning item created: {text}",
                                }
                            )
                            messages.append({"role": "system", "content": "--"})
                    # Handle message outputs
                    elif evt_name == "message_output_created":
                        messages.append(
                            {
                                "role": "assistant",
                                "content": event.item.raw_item.content[0].text,
                            }
                        )
                    # Unknown events can be ignored or logged here
                    render_messages()

                thinking_active = False
                await thinking_task
                messages.pop()

            except (KeyboardInterrupt, EOFError):
                continue_loop = False
