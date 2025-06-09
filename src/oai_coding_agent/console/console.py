import asyncio
from typing import Protocol

from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout import Layout as PTLayout
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from oai_coding_agent.agent import AgentProtocol
from oai_coding_agent.agent.events import UsageUpdateEvent
from oai_coding_agent.console.key_bindings import (
    get_bg_prompt_key_bindings,
    get_key_bindings,
)
from oai_coding_agent.console.rendering import clear_terminal, console
from oai_coding_agent.console.rendering import render_message as original_render_message
from oai_coding_agent.console.slash_commands import (
    handle_slash_command,
    register_slash_commands,
)
from oai_coding_agent.console.state import UIMessage, UIState
from oai_coding_agent.console.ui_event_mapper import map_event_to_ui_message
from oai_coding_agent.runtime_config import get_data_dir


class Console(Protocol):
    """Common interface for console interactions."""

    agent: AgentProtocol

    async def run(self) -> None:
        pass


class HeadlessConsole:
    """Console that runs headless (single prompt) mode."""

    def __init__(self, agent: AgentProtocol) -> None:
        self.agent = agent

    async def run(self) -> None:
        """
        Execute one prompt in async 'headless' mode and render streamed output.
        """
        if not self.agent.config.prompt:
            raise ValueError("Prompt is required for headless mode")

        console.print(f"[bold cyan]Prompt:[/bold cyan] {self.agent.config.prompt}")
        async with self.agent:
            event_stream, _ = await self.agent.run(self.agent.config.prompt)
            async for event in event_stream:
                ui_msg = map_event_to_ui_message(event)
                if ui_msg:
                    original_render_message(ui_msg)


class ReplConsole:
    """Console that runs interactive REPL mode."""

    def __init__(self, agent: AgentProtocol) -> None:
        self.agent = agent

    def _format_message(self, msg: UIMessage) -> str:
        """Format a UI message for display in the live panel."""
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        if role == "user":
            return f"[bold blue]You:[/bold blue] {content}"
        elif role == "assistant":
            return f"[bold cyan]oai:[/bold cyan] {content}"
        elif role == "system":
            return f"[dim yellow]System:[/dim yellow] [yellow]{content}[/yellow]"
        elif role == "thought":
            return f"[italic dim]{content}[/italic dim]"
        elif role == "tool":
            return f"[dim green]Tool: {content}[/dim green]"
        return content

    async def run(self) -> None:
        """Interactive REPL loop for the console interface."""
        state = UIState()
        clear_terminal()

        register_slash_commands(state)

        console.print(
            Panel(
                f"[bold cyan]╭─ OAI CODING AGENT ─╮[/bold cyan]\n\n"
                f"[dim]Current Directory:[/dim] [dim cyan]{self.agent.config.repo_path}[/dim cyan]\n"
                f"[dim]Model:[/dim] [dim cyan]{self.agent.config.model.value}[/dim cyan]\n"
                f"[dim]Mode:[/dim] [dim cyan]{self.agent.config.mode.value}[/dim cyan]",
                expand=False,
            )
        )

        # Store prompt history under the XDG data directory
        history_dir = get_data_dir()
        history_dir.mkdir(parents=True, exist_ok=True)
        history_path = history_dir / "prompt_history"

        prompt_session: PromptSession[str] = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
            complete_while_typing=True,
            completer=WordCompleter([f"/{c}" for c in state.slash_commands]),
            complete_in_thread=True,
            key_bindings=get_key_bindings(),
            style=Style.from_dict(
                {"prompt": "ansicyan bold", "auto-suggestion": "#888888"}
            ),
            erase_when_done=True,
        )

        async with self.agent:
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

                    event_stream, result = await self.agent.run(user_input)

                    # Track token usage
                    token_count = {"input": 0, "output": 0, "total": 0}
                    messages_buffer = []

                    def create_status_panel() -> Panel:
                        """Create a panel showing token count and interrupt instruction."""
                        table = Table(show_header=False, box=None, padding=0)
                        table.add_column()
                        table.add_row(Text("Press ESC to interrupt", style="dim italic"))
                        table.add_row(Text(f"Tokens - Input: {token_count['input']:,} | Output: {token_count['output']:,} | Total: {token_count['total']:,}", style="cyan"))
                        return Panel(table, title="[bold]Status[/bold]", border_style="blue")

                    # Consume the event stream in its own task (so it can be cancelled).
                    async def _consume_stream() -> None:
                        with Live(create_status_panel(), console=console, refresh_per_second=4) as live:
                            async for event in event_stream:
                                # Check if it's a usage update event
                                if isinstance(event, UsageUpdateEvent):
                                    token_count["input"] = event.input_tokens
                                    token_count["output"] = event.output_tokens
                                    token_count["total"] = event.total_tokens
                                    # Update the live display with new token counts
                                    live.update(create_status_panel())
                                else:
                                    ui_msg = map_event_to_ui_message(event)
                                    if ui_msg:
                                        messages_buffer.append(ui_msg)
                                        # Update the display
                                        layout = Layout()
                                        layout.split_column(
                                            Layout(name="messages"),
                                            Layout(create_status_panel(), size=4, name="status")
                                        )
                                        # Render accumulated messages
                                        messages_display = ""
                                        for msg in messages_buffer[-10:]:  # Show last 10 messages
                                            messages_display += self._format_message(msg) + "\n\n"
                                        layout["messages"].update(Panel(messages_display.strip(), border_style="dim"))
                                        live.update(layout)
                        
                        # After streaming completes, print all messages normally
                        for msg in messages_buffer:
                            original_render_message(msg)

                    # Create a fresh mini application each time
                    bg_prompt_app: Application[None] = Application(
                        layout=PTLayout(TextArea("", focusable=False)),
                        key_bindings=get_bg_prompt_key_bindings(state),
                        full_screen=False,
                        mouse_support=False,
                        erase_when_done=True,
                        output=None,
                    )

                    # Mini application that keeps key bindings alive during streaming
                    async def _run_mini_app() -> None:
                        await bg_prompt_app.run_async()

                    # Schedule both tasks.
                    stream_llm_task = asyncio.create_task(_consume_stream())
                    bg_prompt_task = asyncio.create_task(_run_mini_app())

                    state.set_running_task(
                        stream_llm_task,
                        result,
                        getattr(self.agent, "_previous_response_id", None),
                    )

                    try:
                        # Wait until either the stream finishes or the user interrupts.
                        done, pending = await asyncio.wait(
                            {stream_llm_task, bg_prompt_task},
                            return_when=asyncio.FIRST_COMPLETED,
                        )

                        # Clean up the remaining tasks
                        for task in pending:
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass

                        # Ensure mini application is properly exited
                        if not bg_prompt_task.done():
                            bg_prompt_app.exit()
                    finally:
                        state.cancel_current_task()
                        if state.interrupted:
                            self.agent._previous_response_id = (
                                state.last_completed_response_id
                            )

                except (KeyboardInterrupt, EOFError):
                    continue_loop = False
