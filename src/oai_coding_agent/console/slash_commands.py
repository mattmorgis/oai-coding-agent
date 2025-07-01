from dataclasses import dataclass
from typing import Awaitable, Callable, Generator, List, Optional, Sequence

from prompt_toolkit.application import in_terminal
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.styles import Style

from oai_coding_agent.console.github_console import GitHubConsole
from oai_coding_agent.console.github_workflow_console import GitHubWorkflowConsole
from oai_coding_agent.runtime_config import RuntimeConfig


@dataclass(frozen=True)
class SlashCommand:
    """Definition of a slash command."""

    name: str  # e.g. "/help"
    description: str
    handler: Callable[[Sequence[str]], Awaitable[None]]  # Args tokens after the command


class SlashCommandHandler:
    """Encapsulates slash-commands: completion, suggestion, handling and style settings."""

    style: Style = Style.from_dict(
        {
            "completion-menu": "noinherit",
            "completion-menu.completion": "noinherit",
            "completion-menu.scrollbar": "noinherit",
            "completion-menu.completion.current": "noinherit bold",
            "scrollbar": "noinherit",
            "scrollbar.background": "noinherit",
            "scrollbar.button": "noinherit",
            "bottom-toolbar": "noreverse",
            "auto-suggestion": "dim",
        }
    )

    def __init__(
        self, printer: Callable[[str, str], None], config: RuntimeConfig
    ) -> None:
        self._printer = printer
        self._config = config

        # Helper handler for unimplemented commands
        async def _todo(_: Sequence[str]) -> None:
            self._printer("Not implemented yet\n", "yellow")

        self._commands: List[SlashCommand] = [
            SlashCommand(
                "/vim", "Toggle between vim and emacs mode (default is emacs)", _todo
            ),
            SlashCommand(
                "/clear", "Clear conversation history and free up context", _todo
            ),
            SlashCommand(
                "/cost",
                "Show the total cost and duration of the current session",
                _todo,
            ),
            SlashCommand(
                "/github-login",
                "Login to GitHub",
                self._cmd_github_login,
            ),
            SlashCommand(
                "/github-logout",
                "Logout from GitHub",
                self._cmd_github_logout,
            ),
            SlashCommand(
                "/install-workflow",
                "Install GitHub App for workflow access",
                self._cmd_install_workflow,
            ),
            SlashCommand("/help", "Show help and available commands", self._cmd_help),
        ]

        # Dict for O(1) lookups
        self._commands_by_base = {
            cmd.name.split()[0].lower(): cmd for cmd in self._commands
        }

    # ---------------------------------------------------------------------
    # Command Handlers
    # ---------------------------------------------------------------------
    async def _cmd_help(self, _args: Sequence[str]) -> None:
        """Show list of available slash-commands."""
        lines = [f"{cmd.name:<18} {cmd.description}" for cmd in self._commands]
        help_text = "Available commands:\n\n" + "\n".join(lines) + "\n"
        self._printer(help_text, "cyan")

    async def _cmd_github_login(self, _args: Sequence[str]) -> None:
        """Login to GitHub using browser-based flow."""
        print("Logging in to GitHub...")
        github_console = GitHubConsole()
        github_console.check_or_authenticate()

    async def _cmd_github_logout(self, _args: Sequence[str]) -> None:
        """Logout from GitHub by removing stored token."""
        github_console = GitHubConsole()
        github_console.logout()

    async def _cmd_install_workflow(self, _args: Sequence[str]) -> None:
        """Install GitHub App for workflow access."""
        workflow_console = GitHubWorkflowConsole(self._config)
        await workflow_console.run()

    @property
    def completer(self) -> Completer:
        handler = self

        class _SlashCompleter(Completer):
            def get_completions(
                self, document: Document, complete_event: CompleteEvent
            ) -> Generator[Completion, None, None]:
                text = document.text
                if document.cursor_position_row != 0 or not text.startswith("/"):
                    return
                for cmd in handler._commands:
                    base = cmd.name.split()[0]
                    if base.lower().startswith(text.lower()):
                        display = f"{cmd.name:<20} {cmd.description}"
                        yield Completion(
                            base, start_position=-len(text), display=display
                        )

        return _SlashCompleter()

    @property
    def auto_suggest(self) -> AutoSuggest:
        handler = self

        class _SlashAutoSuggest(AutoSuggest):
            def get_suggestion(
                self, buffer: Buffer, document: Document
            ) -> Optional[Suggestion]:
                text = document.text
                if (
                    document.cursor_position_row != 0
                    or not text.startswith("/")
                    or len(text) <= 1
                ):
                    return None
                for cmd in handler._commands:
                    base = cmd.name.split()[0]
                    if (
                        base.lower().startswith(text.lower())
                        and base.lower() != text.lower()
                    ):
                        return Suggestion(base[len(text) :])
                return None

        return _SlashAutoSuggest()

    @staticmethod
    def on_completions_changed(buf: Buffer) -> None:
        state = buf.complete_state
        if state and state.complete_index is None:
            state.complete_index = 0

    async def handle(self, user_input: str) -> bool:
        """Process a slash command; returns True if handled (only if valid command)."""
        text = user_input.strip()
        if not text.startswith("/"):
            return False
        # Extract base (first token) and dispatch.
        parts = text.split()
        base = parts[0].lower()
        cmd = self._commands_by_base.get(base)
        if not cmd:
            return False  # Not a recognised slash-command

        # Call the registered handler with remaining args (if any)
        try:
            async with in_terminal():
                await cmd.handler(parts[1:])
        except Exception as exc:  # noqa: BLE001
            self._printer(f"error: {exc}\n", "red")
        return True
