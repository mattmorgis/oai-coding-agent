from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys

from oai_coding_agent.console.state import UIState


def get_key_bindings() -> KeyBindings:
    """Return the custom KeyBindings (e.g. Tab behaviour).

    Args:
        state: Optional UI state to track running tasks for interruption
    """
    kb = KeyBindings()

    @kb.add(Keys.Tab)
    def _(event: KeyPressEvent) -> None:
        buffer = event.current_buffer
        suggestion = buffer.suggestion
        if suggestion:
            buffer.insert_text(suggestion.text)
        else:
            buffer.complete_next()

    # Support Shift+Enter (mapped to Ctrl+J in your terminal) for newline without submission.
    @kb.add("c-j", eager=True)
    def _(event: KeyPressEvent) -> None:
        """Insert newline on Ctrl+J (recommended Shift+Enter mapping in terminal)."""
        event.current_buffer.insert_text("\n")

    # Support Alt+Enter for newline without submission.
    @kb.add(Keys.Escape, Keys.Enter, eager=True)
    def _(event: KeyPressEvent) -> None:
        """Insert newline on Alt+Enter."""
        event.current_buffer.insert_text("\n")

    # Enter submits input
    @kb.add(Keys.Enter, eager=True)
    def _(event: KeyPressEvent) -> None:
        """Submit input on Enter"""
        event.current_buffer.validate_and_handle()

    return kb


# This is to get the key bindings to work during background streaming.
def get_bg_prompt_key_bindings(state: UIState) -> KeyBindings:
    """Return the custom KeyBindings during background streaming.

    Args:
        state: Optional UI state to track running tasks for interruption
    """
    kb = KeyBindings()

    @kb.add(Keys.Escape, eager=True)
    def interrupt(_: KeyPressEvent) -> None:
        """Handle Ctrl+C to cancel running tasks."""
        if state.current_stream_task:
            state.cancel_current_task()
            state.interrupted = True

    return kb
