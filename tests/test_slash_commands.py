import pytest
from rich.console import Console

import oai_coding_agent.console.rendering as rendering
import oai_coding_agent.console.slash_commands as _sc
from oai_coding_agent.console.slash_commands import (
    handle_slash_command,
    register_slash_commands,
)
from oai_coding_agent.console.state import UIState


@pytest.fixture(autouse=True)
def record_console(monkeypatch: pytest.MonkeyPatch) -> Console:
    """Replace rendering.console and clear_terminal to no-ops and capture output."""
    recorder = Console(record=True, width=80)
    monkeypatch.setattr(rendering, "console", recorder)
    monkeypatch.setattr(rendering, "clear_terminal", lambda: None)
    # Also patch slash_commands.clear_terminal (imported at module load)

    monkeypatch.setattr(_sc, "clear_terminal", lambda: None)
    return recorder


def test_register_slash_commands_populates_commands() -> None:
    state = UIState()
    register_slash_commands(state)
    expected = {"help", "clear", "exit", "quit", "version"}
    assert expected.issubset(set(state.slash_commands.keys()))


def test_handle_help_command_returns_true() -> None:
    state = UIState()
    register_slash_commands(state)
    cont = handle_slash_command(state, "/help")
    assert cont is True


def test_handle_clear_command_returns_true() -> None:
    state = UIState()
    register_slash_commands(state)
    cont = handle_slash_command(state, "/clear")
    assert cont is True


def test_handle_exit_command_returns_false() -> None:
    state = UIState()
    register_slash_commands(state)
    cont = handle_slash_command(state, "/exit")
    assert cont is False


def test_handle_unknown_command_returns_true() -> None:
    state = UIState()
    register_slash_commands(state)
    cont = handle_slash_command(state, "/nonexistent arg")
    assert cont is True
