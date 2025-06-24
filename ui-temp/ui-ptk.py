#!/usr/bin/env python3
"""A Prompt-toolkit first UI where Rich log lines are printed above a two-line
prompt (spinner + input).  The spinner never fights for the cursor because it
is rendered by PTK itself, not by Rich.

Run:  python ui-ptk.py
Press <Esc> while the assistant is working to abort the current answer.
"""

from __future__ import annotations

import asyncio
import itertools
import random
import sys
from typing import AsyncGenerator, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

console = Console()

# Spinner frames (same cadence Rich uses for "dots") -------------------------
SPIN_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
spin_cycle = itertools.cycle(SPIN_FRAMES)


# ──────────────────────────── assistant simulation ──────────────────────────
async def get_assistant_response(
    user_input: str,
) -> AsyncGenerator[tuple[str, str], None]:
    """Fake streaming events coming from an LLM-powered agent."""
    events = [
        ("thinking", "Analyzing the request…"),
        ("file_read", "Reading config.py"),
        ("thinking", "Understanding the current code structure…"),
        ("file_edit", "Editing main.py line 42"),
        ("command", "Running: python -m pytest"),
        ("thinking", "Tests passed, preparing response…"),
    ]

    for etype, content in events:
        await asyncio.sleep(random.uniform(0.3, 1.0))
        yield etype, content

    await asyncio.sleep(random.uniform(0.5, 1.0))
    yield "response", f"I've processed your request: “{user_input}”"


# ─────────────────────────────── global state ───────────────────────────────
spinner_text: Optional[str] = None  # none → spinner hidden
spinner_frame: str = next(spin_cycle)

# Will be assigned from main() so other coroutines can invalidate the UI.
session: PromptSession

# Flag set by the ESC key to ask the worker to cancel the current request.
cancel_current: bool = False


# ──────────────────────────────── prompt fn ─────────────────────────────────


def prompt_fragments() -> ANSI:
    """Return spinner + prompt.  Called by PTK every render cycle."""
    if spinner_text is None:
        return ANSI("\n> ")

    # First line: cyan spinner + status, Second line: actual prompt
    line1 = f"\x1b[36m{spinner_frame} {spinner_text}\x1b[0m"
    return ANSI(f"\n{line1}\n> ")


# ───────────────────────────── spinner animator ─────────────────────────────


async def spinner_task() -> None:
    """Animate the spinner while it is visible."""
    global spinner_frame
    while True:
        if spinner_text is not None:  # only spin while the assistant is busy
            spinner_frame = next(spin_cycle)
            session.app.invalidate()
        await asyncio.sleep(0.1)


# ───────────────────────────── event pretty-print ───────────────────────────


def print_event(event_type: str, content: str) -> None:
    if event_type == "thinking":
        console.print(f"[dim italic]💭 {content}[/dim italic]")
    elif event_type == "file_read":
        console.print(f"[blue]📖 {content}[/blue]")
    elif event_type == "file_edit":
        console.print(f"[yellow]✏️  {content}[/yellow]")
    elif event_type == "command":
        console.print(f"[magenta]⚡ {content}[/magenta]")
    elif event_type == "response":
        console.print(f"[bold green]Assistant:[/] {content}")
        # TODO: if message in queue, print blank line


# ─────────────────────────────── agent worker ───────────────────────────────


async def agent_worker(message_q: asyncio.Queue[str | None]) -> None:
    """Consume user prompts, stream assistant events, honour cancellation."""
    global spinner_text, cancel_current

    while True:
        user_prompt = await message_q.get()
        if user_prompt is None:  # shutdown
            break

        spinner_text = "Starting…"
        session.app.invalidate()
        # await run_in_terminal(lambda: console.print())  # blank line

        async for etype, content in get_assistant_response(user_prompt):
            if cancel_current:
                await run_in_terminal(lambda: console.print("[red]Cancelled.[/red]"))
                cancel_current = False
                break

            # update spinner label and print log above prompt
            spinner_text = content
            await run_in_terminal(lambda et=etype, c=content: print_event(et, c))
            session.app.invalidate()

            if etype == "response":
                break

        # finished (either normally or cancelled)
        spinner_text = None
        session.app.invalidate()
        # await run_in_terminal(lambda: console.print())  # blank line
        message_q.task_done()


# ─────────────────────────── key bindings (ESC = cancel) ────────────────────

kb = KeyBindings()


@kb.add("escape")
def _(event: KeyPressEvent) -> None:  # noqa: D401  (simple name _ is fine)
    """ESC requests cancellation of the current assistant response."""
    global cancel_current
    if spinner_text is not None:
        cancel_current = True


# ─────────────────────────────────── main ────────────────────────────────────


async def main() -> None:  # noqa: C901 (keep everything together for clarity)
    global session

    message_q: asyncio.Queue[str | None] = asyncio.Queue()

    session = PromptSession(
        message=prompt_fragments,
        multiline=False,
        erase_when_done=True,
        key_bindings=kb,
        reserve_space_for_menu=1,  # don’t steal too many rows
    )

    # Start background tasks --------------------------------------------------
    tasks: list[asyncio.Task] = [
        asyncio.create_task(spinner_task(), name="spinner"),
        asyncio.create_task(agent_worker(message_q), name="agent_worker"),
    ]

    with patch_stdout(raw=True):  # make print() & Rich coexist with PTK
        try:
            while True:
                try:
                    user_input = await session.prompt_async()
                except EOFError:
                    raise KeyboardInterrupt  # treat Ctrl-D like Ctrl-C

                if not user_input.strip():
                    continue

                await run_in_terminal(lambda: console.print())  # spacer
                await run_in_terminal(
                    lambda ui=user_input: console.print(f"[bold cyan]>[/] {ui}")
                )
                await run_in_terminal(lambda: console.print())  # spacer
                await message_q.put(user_input)

        except (KeyboardInterrupt, asyncio.CancelledError):
            # graceful shutdown ------------------------------------------------
            await run_in_terminal(
                lambda: console.print("\n[yellow]Shutting down…[/yellow]")
            )
            await message_q.put(None)
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await run_in_terminal(lambda: console.print("[yellow]Goodbye![/yellow]"))
            sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
