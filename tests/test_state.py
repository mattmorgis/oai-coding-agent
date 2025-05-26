import pytest

from oai_coding_agent.console.state import UIState


def test_ui_state_initializes_empty():
    state = UIState()
    assert isinstance(state.messages, list)
    assert state.messages == []
    assert isinstance(state.slash_commands, dict)
    assert state.slash_commands == {}
    assert state.config == {"vim_mode": False}
    assert state.prompt_session is None
