"""Tests for ui_event_mapper module."""

from oai_coding_agent.agent.events import (
    MessageOutputEvent,
    ReasoningEvent,
    ToolCallEvent,
)
from oai_coding_agent.console.ui_event_mapper import map_event_to_ui_message


def test_map_tool_call_event() -> None:
    """Test mapping of tool call events."""
    event = ToolCallEvent(name="cmd", arguments="a, b")
    mapped = map_event_to_ui_message(event)
    assert mapped == {"role": "tool", "content": "cmd(a, b)"}


def test_map_reasoning_event() -> None:
    """Test mapping of reasoning events."""
    event = ReasoningEvent(text="thinking about the problem")
    mapped = map_event_to_ui_message(event)
    assert mapped == {"role": "thought", "content": "💭 thinking about the problem"}


def test_map_message_output_event() -> None:
    """Test mapping of message output events."""
    event = MessageOutputEvent(text="Here is the output")
    mapped = map_event_to_ui_message(event)
    assert mapped == {"role": "assistant", "content": "Here is the output"}
