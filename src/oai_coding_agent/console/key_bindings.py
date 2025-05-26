from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys


def get_key_bindings() -> KeyBindings:
    """Return the custom KeyBindings (e.g. Tab behaviour)."""
    kb = KeyBindings()

    @kb.add(Keys.Tab)
    def _(event):
        buffer = event.current_buffer
        suggestion = buffer.suggestion
        if suggestion:
            buffer.insert_text(suggestion.text)
        else:
            buffer.complete_next()

    return kb
