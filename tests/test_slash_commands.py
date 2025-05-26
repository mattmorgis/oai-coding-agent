import pytest
from rich.console import Console

from oai_coding_agent.console.state import UIState
from oai_coding_agent.console.slash_commands import (
    register_slash_commands,
    handle_slash_command,
)
import oai_coding_agent.console.rendering as rendering


@pytest.fixture(autouse=True)
def record_console(monkeypatch):
    """Replace rendering.console and clear_terminal to no-ops and capture output."""
    recorder = Console(record=True, width=80)
    monkeypatch.setattr(rendering, "console", recorder)
    monkeypatch.setattr(rendering, "clear_terminal", lambda: None)
    # Also patch slash_commands.clear_terminal (imported at module load)
    import oai_coding_agent.console.slash_commands as _sc

    monkeypatch.setattr(_sc, "clear_terminal", lambda: None)
    return recorder


def test_register_slash_commands_populates_commands():
    state = UIState()
    register_slash_commands(state)
    expected = {"help", "clear", "exit", "quit", "version"}
    assert expected.issubset(set(state.slash_commands.keys()))


def test_handle_help_command_appends_help_message(record_console):
    state = UIState()
    register_slash_commands(state)
    cont = handle_slash_command(state, "/help")
    assert cont is True
    assert state.messages
    msg = state.messages[-1]
    assert msg["role"] == "system"
    assert "/help - Show help information for available commands." in msg["content"]


def test_handle_clear_command_clears_messages(record_console):
    state = UIState()
    state.messages.append({"role": "user", "content": "hi"})
    register_slash_commands(state)
    cont = handle_slash_command(state, "/clear")
    assert cont is True
    assert len(state.messages) == 1
    assert state.messages[0]["content"] == "Chat history has been cleared."


def test_handle_exit_command_returns_false(record_console):
    state = UIState()
    register_slash_commands(state)
    cont = handle_slash_command(state, "/exit")
    assert cont is False


def test_handle_unknown_command_appends_unknown(record_console):
    state = UIState()
    register_slash_commands(state)
    cont = handle_slash_command(state, "/nonexistent arg")
    assert cont is True
    msg = state.messages[-1]
    assert "Unknown command: /nonexistent" in msg["content"]
