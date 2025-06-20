import os

from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Heading, Markdown

from oai_coding_agent.console.ui_event_mapper import UIMessage


# Classes to override the default Markdown renderer
class PlainHeading(Heading):
    """Left-aligned, no panel."""

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        self.text.justify = "left"
        yield self.text


class PlainMarkdown(Markdown):
    elements = Markdown.elements.copy()
    elements["heading_open"] = PlainHeading


# Apply override globally for Markdown
Markdown.elements["heading_open"] = PlainHeading


console = Console()


def clear_terminal() -> None:
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def render_message(msg: UIMessage) -> None:
    """Render a single message via Rich."""
    role = msg.get("role")
    content = msg.get("content", "")
    if role == "assistant":
        console.print("[bold cyan]oai:[/bold cyan]", end=" ")
        md = Markdown(content, code_theme="nord", hyperlinks=True)
        console.print(md)
    elif role == "thought":
        md = Markdown(content, code_theme="nord", hyperlinks=True, style="dim")
        console.print(md)
        console.print()
    elif role == "tool":
        console.print("[dim]tool›[/dim]", end=" ")
        console.print(f"[dim green]{content}[/dim green]")
        console.print()
    elif role == "error":
        console.print(f"[bold red]error: {content}[/bold red]")
        console.print()
