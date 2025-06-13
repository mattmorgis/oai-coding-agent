from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys


def get_key_bindings() -> KeyBindings:
    """Return the custom KeyBindings (e.g. Tab behaviour)."""
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
