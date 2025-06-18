#!/usr/bin/env python3

from typing import Generator, Optional

from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import completion_is_selected, has_completions
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.styles import Style

commands = [
    ("/add-dir", "Add a new working directory"),
    ("/bug", "Submit feedback about Claude Code"),
    ("/clear", "Clear conversation history and free up context"),
    (
        "/compact",
        "Clear conversation history but keep a summary in context. Optional: /compact [instructions for summarization]",
    ),
    ("/config (theme)", "Open config panel"),
    ("/cost", "Show the total cost and duration of the current session"),
    ("/doctor", "Checks the health of your Claude Code installation"),
    ("/exit (quit)", "Exit the REPL"),
    ("/help", "Show help and available commands"),
    ("/ide", "Manage IDE integrations and show status"),
]


class SlashCompleter(Completer):
    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Generator[Completion, None, None]:
        text = document.text

        # Only complete if we're on the first line and text starts with /
        if document.cursor_position_row == 0 and text.startswith("/"):
            for cmd, desc in commands:
                base_cmd = cmd.split()[0]
                if base_cmd.lower().startswith(text.lower()):
                    # Format: left-align command in 20 chars, then description
                    display = f"{cmd:<20} {desc}"

                    yield Completion(
                        base_cmd,
                        start_position=-len(text),
                        display=display,
                    )


class SlashAutoSuggest(AutoSuggest):
    """Auto-suggest for slash commands."""

    def get_suggestion(
        self, buffer: Buffer, document: Document
    ) -> Optional[Suggestion] | None:
        text = document.text

        # Only suggest if we're on first line and text starts with /
        if document.cursor_position_row == 0 and text.startswith("/") and len(text) > 1:
            for cmd, desc in commands:
                base_cmd = cmd.split()[0]
                if (
                    base_cmd.lower().startswith(text.lower())
                    and base_cmd.lower() != text.lower()
                ):
                    # Return the rest of the command as suggestion
                    return Suggestion(base_cmd[len(text) :])

        return None


# Minimal style - let terminal colors show through more
style = Style.from_dict(
    {
        "completion-menu": "noinherit",
        "completion-menu.completion": "noinherit",
        "completion-menu.scrollbar": "noinherit",
        "completion-menu.completion.current": "noinherit bold",
        "scrollbar": "noinherit",
        "scrollbar.background": "noinherit",
        "scrollbar.button": "noinherit",
        "bottom-toolbar": "noreverse",  # Remove reverse coloring
    }
)
kb = KeyBindings()


@kb.add("enter", filter=has_completions)
def insert_or_accept(event: KeyPressEvent) -> None:
    buf = event.current_buffer
    state = buf.complete_state
    if not completion_is_selected():  # user never arrowed/tabbed
        state.complete_index = state.complete_index or 0  # type: ignore
    buf.apply_completion(state.current_completion)  # type: ignore
    buf.cancel_completion()  # close menu; second Enter will submit
    buf.validate_and_handle()


@kb.add("tab", filter=has_completions)
def accept_or_cycle(event: KeyPressEvent) -> None:
    buf = event.current_buffer
    state = buf.complete_state  # type: ignore

    if len(state.completions) == 1:  # type: ignore
        # One suggestion → treat Tab like “auto-complete”.
        if state.current_completion is None:  # type: ignore
            state.complete_index = 0  # type: ignore
        buf.apply_completion(state.current_completion)  # type: ignore
        buf.cancel_completion()  # close the list
    else:
        # Multiple suggestions → fall back to the usual “cycle to next”.
        buf.complete_next()


print("\033[90mTips for getting started:\n")
print("1. Run /init to create a CLAUDE.md file with instructions for Claude")
print("2. Use Claude to help with file analysis, editing, bash commands and git")
print("3. Be as specific as you would with another engineer for the best results")
print("4. ✓ Run /terminal-setup to set up terminal integration\033[0m\n")


def on_completions_changed(buf: Buffer) -> None:
    state = buf.complete_state
    if state and state.complete_index is None:
        state.complete_index = 0  # visually select the first option


session: PromptSession[str] = PromptSession(
    completer=SlashCompleter(),
    auto_suggest=SlashAutoSuggest(),
    complete_while_typing=True,
    style=style,
    history=InMemoryHistory(),
    vi_mode=False,
    key_bindings=kb,
)

buf = session.default_buffer
buf.on_completions_changed += on_completions_changed  # add a tiny callback

while True:
    try:
        user_input = session.prompt("> ")

        if user_input.strip() in ["/exit", "/quit"]:
            break
        elif user_input.strip():
            print(f"Executing: {user_input}")

    except (KeyboardInterrupt, EOFError):
        break

print("Goodbye!")
