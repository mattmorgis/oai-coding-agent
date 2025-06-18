#!/usr/bin/env python3
"""
CLI Agent Logging Demo (prompt_toolkit ≥ 3.0)
Area 1: scroll-back  •  Area 2: live status  •  Area 3: prompt
"""

import asyncio
import time

from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.widgets import TextArea
from rich.console import Console

# ── Rich console for pretty printing ───────────────────────────────────────────
console = Console()


# ── Animated Components ────────────────────────────────────────────────────────
class EasedTokenCounter:
    def __init__(self, initial_input=0, initial_output=0):
        self.target_input = initial_input
        self.target_output = initial_output
        self.current_input = float(initial_input)
        self.current_output = float(initial_output)
        self.animation_speed = 8.0  # tokens per frame

    def set_targets(self, new_input, new_output):
        """Set new target values to animate towards."""
        self.target_input = new_input
        self.target_output = new_output

    def update(self):
        """Update current values towards targets. Returns True if still animating."""
        input_diff = self.target_input - self.current_input
        output_diff = self.target_output - self.current_output

        # Ease towards target
        if abs(input_diff) > 0.5:
            self.current_input += input_diff * 0.15
        else:
            self.current_input = self.target_input

        if abs(output_diff) > 0.5:
            self.current_output += output_diff * 0.15
        else:
            self.current_output = self.target_output

        # Return True if still animating
        return abs(input_diff) > 0.5 or abs(output_diff) > 0.5

    @property
    def display_text(self):
        return f"Input: {int(self.current_input):,} │ Output: {int(self.current_output):,} tokens"


class Timer:
    def __init__(self):
        self.start_time = None
        self.elapsed = 0.0

    def start(self):
        """Start the timer."""
        self.start_time = time.time()
        self.elapsed = 0.0

    def stop(self):
        """Stop the timer."""
        self.start_time = None

    def update(self):
        """Update elapsed time. Returns True if timer is running."""
        if self.start_time:
            self.elapsed = time.time() - self.start_time
            return True
        return False

    @property
    def display_text(self):
        return f"{self.elapsed:.1f}s"


class Spinner:
    def __init__(self):
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.frame_index = 0
        self.is_spinning = False

    def start(self):
        """Start spinning."""
        self.is_spinning = True
        self.frame_index = 0

    def stop(self):
        """Stop spinning."""
        self.is_spinning = False

    def update(self):
        """Update spinner frame. Returns True if spinning."""
        if self.is_spinning:
            self.frame_index = (self.frame_index + 1) % len(self.frames)
            return True
        return False

    @property
    def current_frame(self):
        return self.frames[self.frame_index] if self.is_spinning else "✓"


class LiveStatus:
    def __init__(self, app, text_area):
        self.app = app
        self.text_area = text_area
        self.token_counter = EasedTokenCounter(1247, 892)
        self.timer = Timer()
        self.spinner = Spinner()
        self.status_text = "Idle"
        self.detail_text = "Ready for commands"
        self.animation_task = None
        self._should_stop = False

    def start_animation_loop(self):
        """Start the animation update loop."""
        try:
            if not self.animation_task or self.animation_task.done():
                self.animation_task = asyncio.create_task(self._animation_loop())
        except RuntimeError:
            # No event loop running yet - animation will start on first status update
            pass

    async def _animation_loop(self):
        """Main animation loop - updates all animated components."""
        try:
            while not self._should_stop:
                needs_update = False

                # Update all animated components
                if self.token_counter.update():
                    needs_update = True
                if self.timer.update():
                    needs_update = True
                if self.spinner.update():
                    needs_update = True

                # Redraw if any component changed
                if needs_update:
                    self._update_display()
                    self.app.invalidate()

                await asyncio.sleep(0.1)  # 10 FPS
        except asyncio.CancelledError:
            pass  # Clean shutdown

    def set_status(self, status_text, detail_text="", spinning=False):
        """Update the status text and control spinner."""
        # Ensure animation loop is running
        self.start_animation_loop()

        self.status_text = status_text
        self.detail_text = detail_text

        if spinning:
            self.spinner.start()
            self.timer.start()
        else:
            self.spinner.stop()
            self.timer.stop()

        self._update_display()
        self.app.invalidate()

    def stop(self):
        """Stop the animation loop and clean up."""
        self._should_stop = True
        if self.animation_task and not self.animation_task.done():
            self.animation_task.cancel()

    def update_tokens(self, new_input, new_output):
        """Update token counts with smooth animation."""
        self.token_counter.set_targets(new_input, new_output)

    def _update_display(self):
        """Update the live status display."""
        spinner_or_check = self.spinner.current_frame
        status_with_icon = f"{spinner_or_check} {self.status_text}"

        self.text_area.text = f"""┌─ Agent Status ────────────────────────────────┐
│ {status_with_icon:<30} {self.timer.display_text:>8} │
│ {self.token_counter.display_text:<45} │
│ {self.detail_text:<45} │
└───────────────────────────────────────────────┘"""


# ── Job Queue Management ──────────────────────────────────────────────────────
class JobQueue:
    def __init__(self):
        self.queue = []
        self.current_job = None
        self.processing = False

    def add_job(self, job_text):
        """Add a job to the queue."""
        self.queue.append(job_text)

    def cancel_current_job(self):
        """Cancel the currently running job."""
        if self.current_job and not self.current_job.done():
            self.current_job.cancel()
            return True
        return False

    def start_processing(self, app):
        """Start processing jobs from the queue."""
        if not self.processing:
            self.processing = True
            app.create_background_task(self._process_queue(app))

    async def _process_queue(self, app):
        """Process jobs sequentially from the queue."""
        try:
            while self.queue:
                job_text = self.queue.pop(0)
                self.current_job = asyncio.create_task(
                    simulate_agent_work(job_text, app)
                )
                try:
                    await self.current_job
                except asyncio.CancelledError:
                    # Job was cancelled, show status and continue with next
                    if live_status:
                        live_status.set_status(
                            "Cancelled", "Job was cancelled by user", spinning=False
                        )

                    def _log_cancellation():
                        console.print("❌ [bold red]Job cancelled by user[/bold red]")
                        console.print()

                    await run_in_terminal(_log_cancellation)
                    await asyncio.sleep(1)  # Brief pause before next job

                self.current_job = None
        finally:
            self.processing = False
            # Show idle status when queue is empty
            if live_status:
                live_status.set_status("Idle", "Ready for commands", spinning=False)


job_queue = JobQueue()

# ── Global live status ────────────────────────────────────────────────────────
live_status_area = TextArea(
    text="",
    height=4,
    focusable=False,
    wrap_lines=False,
    # style="reverse",
)

live_status = None

# ── Area 3: input field ────────────────────────────────────────────────────────
prompt = TextArea(
    prompt="> ",
    multiline=False,
    wrap_lines=False,
)

# ── Key bindings ───────────────────────────────────────────────────────────────
kb = KeyBindings()


@kb.add("enter")
def _(event):
    """Handle user submitting a command."""
    text = prompt.text.strip()
    if not text:
        return
    prompt.buffer.reset()

    # Add job to queue
    job_queue.add_job(text)

    # Update status to show queue
    if live_status:
        queue_size = len(job_queue.queue)
        if job_queue.current_job and not job_queue.current_job.done():
            queue_text = (
                f"Queue: {queue_size} pending" if queue_size > 0 else "Processing..."
            )
            live_status.set_status("Queued", queue_text, spinning=False)
        else:
            live_status.set_status("Starting", "Preparing to process", spinning=True)

    # Start processing if not already running
    job_queue.start_processing(event.app)


@kb.add("escape")
def _(event):
    """Handle ESC - cancel current job."""
    if job_queue.cancel_current_job():
        console.print("\n🚫 [bold yellow]Cancelling current job...[/bold yellow]")
    else:
        console.print("\n💤 [dim]No job running to cancel[/dim]")


@kb.add("c-c")
def _(event):
    """Handle Ctrl+C - clean shutdown."""
    global live_status
    if live_status:
        live_status.stop()
    event.app.exit()


# ── Rich logging helpers ───────────────────────────────────────────────────────
def log_tool_call(tool_icon, tool_name, params):
    """Log a tool call with rich formatting."""
    console.print(f"{tool_icon} [bold cyan]{tool_name}[/bold cyan]")
    for key, value in params.items():
        console.print(f"   ├─ [dim]{key}:[/dim] {value}")


def log_tool_result(result_text, duration, success=True):
    """Log tool result with rich formatting."""
    icon = "📄" if success else "❌"
    color = "green" if success else "red"
    console.print(
        f"{icon} [bold {color}]{result_text}[/bold {color}] [dim]({duration:.1f}s)[/dim]"
    )
    console.print()


def log_thinking(thought_text):
    """Log agent thinking with rich formatting."""
    console.print("🤔 [bold yellow]Agent Thinking[/bold yellow]")
    console.print(f"   [dim italic]{thought_text}[/dim italic]")
    console.print()


# ── Simulate agent work ────────────────────────────────────────────────────────
async def simulate_agent_work(user_input: str, app: Application):
    """Simulate agent processing with tool calls."""
    global live_status

    # Create live status on first use
    if live_status is None:
        live_status = LiveStatus(app, live_status_area)

    try:
        # Show queue status
        queue_size = len(job_queue.queue)
        queue_text = (
            f"Queue: {queue_size} remaining" if queue_size > 0 else "Processing request"
        )

        # Thinking phase
        live_status.set_status(
            "Model thinking...", f"{queue_text} | {user_input}", spinning=True
        )
        await asyncio.sleep(1.5)

        def _log_initial_thinking():
            log_thinking(f"I need to help the user with: {user_input}")

        await run_in_terminal(_log_initial_thinking)

        # Update tokens from model response
        current_input = live_status.token_counter.target_input
        current_output = live_status.token_counter.target_output
        live_status.update_tokens(current_input + 85, current_output + 42)

        # Simulate a few tool calls
        tools = [
            {
                "icon": "🔧",
                "name": "edit_file",
                "params": {"file": "/src/main.py", "lines": "23-31"},
                "detail": "file: /src/main.py",
                "result": "File updated successfully",
                "duration": 2.1,
                "input_tokens": 120,
                "output_tokens": 15,
            },
            {
                "icon": "📖",
                "name": "read_file",
                "params": {"file": "/tests/test_main.py"},
                "detail": "file: /tests/test_main.py",
                "result": "Read 45 lines from test file",
                "duration": 0.8,
                "input_tokens": 45,
                "output_tokens": 8,
            },
            {
                "icon": "⚡",
                "name": "run_command",
                "params": {"cmd": "python -m pytest", "cwd": "/project"},
                "detail": "cmd: python -m pytest",
                "result": "Tests passed successfully",
                "duration": 3.2,
                "input_tokens": 35,
                "output_tokens": 125,
            },
        ]

        for i, tool in enumerate(tools):
            # Update queue status
            queue_size = len(job_queue.queue)
            queue_suffix = f" | Queue: {queue_size}" if queue_size > 0 else ""

            # Tool called - show in live panel with spinner
            live_status.set_status(
                tool["name"], f"{tool['detail']}{queue_suffix}", spinning=True
            )

            # Simulate tool execution duration
            await asyncio.sleep(tool["duration"])

            # Tool finished - move to permanent log
            def _log_tool_completion(tool=tool):
                log_tool_call(tool["icon"], tool["name"], tool["params"])
                log_tool_result(tool["result"], tool["duration"])

            await run_in_terminal(_log_tool_completion)

            # Update token counts with animation
            current_input = live_status.token_counter.target_input
            current_output = live_status.token_counter.target_output
            live_status.update_tokens(
                current_input + tool["input_tokens"],
                current_output + tool["output_tokens"],
            )

            # Brief pause between tools
            await asyncio.sleep(0.5)

        # Job completed successfully
        def _log_completion():
            console.print("🎉 [bold green]Agent finished task![/bold green]")
            console.print()

        await run_in_terminal(_log_completion)

    except asyncio.CancelledError:
        # Re-raise so the job queue can handle it
        raise


# ── Assemble layout and run ────────────────────────────────────────────────────
layout = HSplit([live_status_area, prompt])
app = Application(
    layout=Layout(layout),
    key_bindings=kb,
    full_screen=False,
)

if __name__ == "__main__":
    with patch_stdout(raw=True):
        console.print("[bold blue]CLI Agent Demo[/bold blue]")
        console.print(
            "Commands: [dim]Enter[/dim] to submit | [dim]ESC[/dim] to cancel job | [dim]Ctrl+C[/dim] to exit"
        )
        console.print("=" * 60)
        console.print()
        try:
            asyncio.run(app.run_async())
        except KeyboardInterrupt:
            pass  # Clean exit on Ctrl+C
        finally:
            # Clean up any remaining tasks
            if live_status:
                live_status.stop()
            if job_queue.current_job and not job_queue.current_job.done():
                job_queue.current_job.cancel()
