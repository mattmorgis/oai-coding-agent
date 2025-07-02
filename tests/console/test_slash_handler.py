from pathlib import Path
from typing import Any, Tuple
from unittest.mock import patch

import pytest
from prompt_toolkit.auto_suggest import Suggestion
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from oai_coding_agent.console.slash_commands import SlashCommandHandler
from oai_coding_agent.runtime_config import ModeChoice, ModelChoice, RuntimeConfig


class DummyPrinter:
    def __init__(self) -> None:
        self.called: bool = False
        self.args: tuple[str, str] | None = None

    def __call__(self, message: str, style: str) -> None:
        self.called = True
        self.args = (message, style)


@pytest.fixture
def runtime_config(tmp_path: Path) -> RuntimeConfig:
    return RuntimeConfig(
        openai_api_key="test-key",
        github_token=None,
        model=ModelChoice.codex_mini_latest,
        repo_path=tmp_path,
        mode=ModeChoice.default,
    )


@pytest.fixture
def handler_and_printer(
    runtime_config: RuntimeConfig,
) -> Tuple[SlashCommandHandler, DummyPrinter]:
    printer = DummyPrinter()
    handler = SlashCommandHandler(printer, runtime_config)
    return handler, printer


async def test_handle_returns_false_for_non_slash(
    handler_and_printer: Tuple[SlashCommandHandler, DummyPrinter],
) -> None:
    handler, printer = handler_and_printer
    assert not await handler.handle("hello world")
    assert not printer.called


async def test_handle_returns_true_and_prints_for_slash(
    handler_and_printer: Tuple[SlashCommandHandler, DummyPrinter],
) -> None:
    handler, printer = handler_and_printer
    user_input = "/clear  "
    assert await handler.handle(user_input)
    assert printer.called
    assert printer.args is not None
    message, style = printer.args
    assert message == "Not implemented yet\n"
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


async def test_handle_with_valid_command_and_args(
    handler_and_printer: Tuple[SlashCommandHandler, DummyPrinter],
) -> None:
    handler, printer = handler_and_printer
    user_input = "/clear some extra args"
    assert await handler.handle(user_input)
    assert printer.called


async def test_handle_with_invalid_command_and_args(
    handler_and_printer: Tuple[SlashCommandHandler, DummyPrinter],
) -> None:
    handler, printer = handler_and_printer
    # Reset printer.called to ensure handler does not print
    printer.called = False
    assert not await handler.handle("/foobar some args")
    assert not printer.called


@pytest.mark.skip(reason="Skipping GitHub workflow installation test")
async def test_install_workflow_command(
    handler_and_printer: Tuple[SlashCommandHandler, DummyPrinter],
) -> None:
    """Test that /install-workflow command is properly handled."""
    handler, printer = handler_and_printer

    with patch(
        "oai_coding_agent.console.slash_commands.GitHubWorkflowConsole"
    ) as mock_console_class:
        mock_console = mock_console_class.return_value
        mock_console.run.return_value = True

        assert await handler.handle("/install-workflow")

        # Verify GitHubWorkflowConsole was created with config and run was called
        mock_console_class.assert_called_once_with(handler._config)
        mock_console.run.assert_called_once()
