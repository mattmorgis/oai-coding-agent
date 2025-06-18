#!/usr/bin/env python3
"""
Three-zone CLI
  • Area-1 = scroll-back log
  • Area-2 = live status
  • Area-3 = > prompt
Adds:
  • Esc      → cancel current agent run
  • Ctrl-C   → quit program cleanly
"""

import asyncio
import random
import signal
import time
from dataclasses import dataclass

from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.widgets import TextArea
from rich.console import Console
from rich.markup import escape

console = Console()


# ───────────────────────────────────────────────────────────────────────────────
@dataclass
class Status:
    tool: str | None = None
    started: float = 0.0
    in_tokens: int = 0
    out_tokens: int = 0
    done: bool = False
    cancelled: bool = False

    def as_text(self) -> str:
        if self.tool is None:
            return "Agent Status\n✓ Idle            0.0 s\n"
        delta = time.time() - self.started
        head = (
            f"{'✖' if self.cancelled else ('✓' if self.done else '*')} "
            f"{self.tool:<15} {delta:4.1f}s"
        )
        tok = f"{self.in_tokens:,} │ Output: {self.out_tokens:,} tokens"
        return f"Agent Status\n{head}\nInput: {tok}"


status = Status()
status_pane = TextArea(
    text=status.as_text(),
    height=3,
    style="bg:#c4cdf8 #000000",
    focusable=False,
    wrap_lines=False,
)


def log(line: str):
    """Print above the UI (Area-1)."""

    def _do():
        console.print(line)

    run_in_terminal(_do)


# ── fake tools / agent routine ────────────────────────────────────────────────
TOOLS = ["read_file", "run_command", "edit_file"]
current_job: asyncio.Task | None = None  # ← pointer for Esc / Ctrl-C


async def run_agent(prompt: str, app: Application):
    global current_job
    try:
        for _ in range(3):
            tool = random.choice(TOOLS)
            log(f"[bold cyan]{tool}[/] ▶ {escape(prompt)}")
            status.tool, status.started = tool, time.time()
            status.done = status.cancelled = False
            status.in_tokens += random.randint(200, 400)

            for _ in range(5):  # pretend streaming
                await asyncio.sleep(0.25)
                status.out_tokens += random.randint(20, 60)
                status_pane.text = status.as_text()
                app.invalidate()

            log(f"[green]✓ {tool} completed ({time.time() - status.started:0.1f}s)")
            status.done = True
            status_pane.text = status.as_text()
            app.invalidate()

        log("[bold yellow]Agent finished all tasks![/]")
    except asyncio.CancelledError:
        status.cancelled = True
        status_pane.text = status.as_text()
        app.invalidate()
        log("[red]✖ Job cancelled by user[/]")
        raise
    finally:
        status.tool = None
        status_pane.text = status.as_text()
        app.invalidate()
        current_job = None


# ── Area-3 prompt & key-bindings ──────────────────────────────────────────────
input_field = TextArea(prompt="> ", multiline=False, wrap_lines=False)
kb = KeyBindings()


@kb.add("enter")
def _(ev):
    global current_job
    text = input_field.text.strip()
    input_field.buffer.reset()
    if not text or current_job:  # ignore if busy or empty
        return
    current_job = ev.app.create_background_task(run_agent(text, ev.app))


@kb.add("escape")
async def _(ev):
    """
    Esc → cancel current job.
    """
    global current_job
    if current_job and not current_job.done():
        current_job.cancel()
        try:
            await current_job
        except asyncio.CancelledError:
            pass  # swallow—handled in run_agent
        current_job = None


@kb.add("c-c")  # Ctrl-C
def _(ev):
    """
    Ctrl-C → clean shutdown.
    """
    global current_job
    if current_job and not current_job.done():
        current_job.cancel()  # best effort
    ev.app.exit(result=None)


# ── assemble & run ────────────────────────────────────────────────────────────
layout = HSplit([status_pane, input_field])
app = Application(layout=Layout(layout), key_bindings=kb, full_screen=False)


def main():
    # Handle real SIGINT as well (so ^C outside PT still quits)
    signal.signal(signal.SIGINT, lambda *_: app.exit())
    with patch_stdout(raw=True):
        asyncio.run(app.run_async())


if __name__ == "__main__":
    main()
