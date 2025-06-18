#!/usr/bin/env python3
"""
Simple chat UI using Rich and Prompt Toolkit
"""

import asyncio
import random
import sys

from prompt_toolkit import PromptSession
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner

console = Console()


async def get_assistant_response(user_input: str):
    """Simulate a coding agent with streaming events"""
    # Simulate various agent actions
    events = [
        ("thinking", "Analyzing the request..."),
        ("file_read", "Reading config.py"),
        ("thinking", "Understanding the current code structure..."),
        ("file_edit", "Editing main.py line 42"),
        ("command", "Running: python test.py"),
        ("thinking", "Tests passed, preparing response..."),
    ]

    for event_type, content in events:
        # Random delay between events
        await asyncio.sleep(random.uniform(0.3, 1.0))
        yield event_type, content

    # Final response
    await asyncio.sleep(random.uniform(0.5, 1.5))
    yield "response", f"I've processed your request: '{user_input}'"


def print_event(event_type: str, content: str) -> None:
    """Print different types of agent events with appropriate styling"""
    if event_type == "thinking":
        console.print(f"[dim italic]💭 {content}[/dim italic]")
    elif event_type == "file_read":
        console.print(f"[blue]📖 {content}[/blue]")
    elif event_type == "file_edit":
        console.print(f"[yellow]✏️  {content}[/yellow]")
    elif event_type == "command":
        console.print(f"[magenta]⚡ {content}[/magenta]")
    elif event_type == "response":
        console.print(f"[bold green]Assistant:[/bold green] {content}")


def create_status_display(status_text: str) -> Spinner:
    """Create a status display with spinner"""
    spinner = Spinner("dots", text=status_text, style="cyan")
    return spinner


def print_header() -> None:
    """Print the header information"""
    console.print(
        Panel.fit(
            "[bold]● Codex[/bold] [dim](research preview) v0.1.2505172129[/dim]",
            padding=(0, 1),
        )
    )

    # Session info
    console.print()
    console.print(
        "[dim]localhost session:[/dim] ac3e81201a0a4583a99e027c3fef04e1", style="cyan"
    )
    console.print(
        "[dim]↳ workdir:[/dim] ~/Developer/agents/oai-coding-agent", style="cyan"
    )
    console.print("[dim]↳ model:[/dim] codex-mini-latest", style="cyan")
    console.print("[dim]↳ provider:[/dim] openai", style="cyan")
    console.print("[dim]↳ approval:[/dim] suggest", style="cyan")
    console.print()


async def main() -> None:
    """Main chat loop"""
    # Clear screen and print header
    console.clear()
    print_header()

    # Message history
    messages = []

    session: PromptSession[str] = PromptSession(
        multiline=False,
        erase_when_done=True,
    )

    try:
        while True:
            # Get user input asynchronously
            user_input = await session.prompt_async("> ")

            # Skip empty input
            if not user_input.strip():
                continue

            # The panel and prompt are already erased by erase_when_done
            # Just print the conversation
            console.print(f"[bold cyan]>[/bold cyan] {user_input}")
            messages.append(("user", user_input))
            console.print()  # Space after user input

            # Show spinner while agent is working
            with Live(
                Spinner("dots", text="Starting...", style="cyan"),
                console=console,
                refresh_per_second=10,
                transient=True,
            ) as live:
                async for event_type, content in get_assistant_response(user_input):
                    if event_type == "response":
                        # Stop the spinner and show final response
                        live.stop()
                        print_event(event_type, content)
                        messages.append(("assistant", content))
                    else:
                        # Update spinner status and show event
                        live.update(Spinner("dots", text=content, style="cyan"))
                        print_event(event_type, content)
                        console.print()

            console.print()  # Space after everything

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Goodbye![/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
