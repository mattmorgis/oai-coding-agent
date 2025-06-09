import os

from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Heading, Markdown

from oai_coding_agent.console.state import UIMessage


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


def render_message(msg: UIMessage) -> str:
    """Render a single message via Rich."""
    role = msg.get("role")
    content = msg.get("content", "")
    if role == "user":
        return f"[bold blue]You:[/bold blue] {content}"
    elif role == "assistant":
        # console.print("[bold cyan]oai:[/bold cyan]", end=" ")
        md = Markdown(content, code_theme="nord", hyperlinks=True)
        return "[bold cyan]oai:[/bold cyan]\n" + md
    elif role == "system":
        return f"[dim yellow]System:[/dim yellow] [yellow]{content}[/yellow]"
    elif role == "thought":
        return f"[italic dim]{content}[/italic dim]"
    elif role == "tool":
        return f"[dim green]Tool: {content}[/dim green]"

    # console.print()
