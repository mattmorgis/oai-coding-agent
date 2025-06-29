from typing import Any, Tuple

import pytest
from prompt_toolkit.auto_suggest import Suggestion
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from oai_coding_agent.console.repl_console import SlashCommandHandler


class DummyPrinter:
    def __init__(self) -> None:
        self.called: bool = False
        self.args: tuple[str, str] | None = None

    def __call__(self, message: str, style: str) -> None:
        self.called = True
        self.args = (message, style)


@pytest.fixture
def handler_and_printer() -> Tuple[SlashCommandHandler, DummyPrinter]:
    printer = DummyPrinter()
    handler = SlashCommandHandler(printer)
    return handler, printer


def test_handle_returns_false_for_non_slash(
    handler_and_printer: Tuple[SlashCommandHandler, DummyPrinter],
) -> None:
    handler, printer = handler_and_printer
    assert not handler.handle("hello world")
    assert not printer.called


def test_handle_returns_true_and_prints_for_slash(
    handler_and_printer: Tuple[SlashCommandHandler, DummyPrinter],
) -> None:
    handler, printer = handler_and_printer
    user_input = "/clear  "
    assert handler.handle(user_input)
    assert printer.called
    assert printer.args is not None
    message, style = printer.args
    assert message == f"Slash command: {user_input}\n"
    assert style == "yellow"


def test_completions_suggest_slash_commands(
    handler_and_printer: Tuple[SlashCommandHandler, DummyPrinter],
) -> None:
    handler, _ = handler_and_printer
    completer = handler.completer
    doc = Document(text="/c", cursor_position=2)
    completions = list(completer.get_completions(doc, CompleteEvent()))
    assert any(c.text == "/clear" for c in completions)


def test_auto_suggest_provides_remainder(
    handler_and_printer: Tuple[SlashCommandHandler, DummyPrinter],
) -> None:
    handler, _ = handler_and_printer
    autosuggester = handler.auto_suggest
    assert (
        autosuggester.get_suggestion(Buffer(), Document(text="/", cursor_position=1))
        is None
    )
    doc = Document(text="/cl", cursor_position=3)
    suggestion = autosuggester.get_suggestion(Buffer(), doc)
    assert isinstance(suggestion, Suggestion)
    assert suggestion.text == "ear"


def test_on_completions_changed_sets_index() -> None:
    buf = Buffer()
    fake_state: Any = type("FakeState", (), {"complete_index": None})()
    buf.complete_state = fake_state
    SlashCommandHandler.on_completions_changed(buf)
    assert fake_state.complete_index == 0
