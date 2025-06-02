"""Tests for ui_event_mapper module."""

from typing import Any
from unittest.mock import Mock

from oai_coding_agent.agent.events import (
    AgentRunItemStreamEvent as RunItemStreamEvent,
    AgentToolCallItem as ToolCallItem,
    AgentReasoningItem as ReasoningItem,
    AgentMessageOutputItem as MessageOutputItem,
)

from oai_coding_agent.console.ui_event_mapper import map_sdk_event_to_ui_message


def create_mock_run_item_event(
    name: str, raw_item: Any, item_type: type
) -> RunItemStreamEvent:
    """Create a mock RunItemStreamEvent with proper item type."""
    event = Mock(spec=RunItemStreamEvent)
    event.type = "run_item_stream_event"
    event.name = name

    # Create a mock item of the specified type
    item = Mock(spec=item_type)
    item.raw_item = raw_item
    event.item = item

    return event


def test_map_sdk_event_tool_called() -> None:
    """Test mapping of tool_called events."""
    raw = Mock()
    raw.name = "cmd"
    raw.arguments = ("a", "b")
    event = create_mock_run_item_event("tool_called", raw, ToolCallItem)
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped == {"role": "tool", "content": "cmd(('a', 'b'))"}


def test_map_sdk_event_reasoning_with_summary() -> None:
    """Test mapping of reasoning events with summary."""
    raw = Mock()
    summary_item = Mock()
    summary_item.text = "thinking"
    raw.summary = [summary_item]
    event = create_mock_run_item_event("reasoning_item_created", raw, ReasoningItem)
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped == {"role": "thought", "content": "💭 thinking"}


def test_map_sdk_event_reasoning_without_summary() -> None:
    """Test mapping of reasoning events without summary."""
    raw = Mock()
    raw.summary = []
    event = create_mock_run_item_event("reasoning_item_created", raw, ReasoningItem)
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped is None


def test_map_sdk_event_reasoning_with_empty_summary() -> None:
    """Test mapping of reasoning events with None summary."""
    raw = Mock()
    raw.summary = None
    event = create_mock_run_item_event("reasoning_item_created", raw, ReasoningItem)
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped is None


def test_map_sdk_event_message_output_created() -> None:
    """Test mapping of message output events."""
    raw = Mock()
    content_item = Mock()
    content_item.text = "output text"
    raw.content = [content_item]
    event = create_mock_run_item_event("message_output_created", raw, MessageOutputItem)
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped == {"role": "assistant", "content": "output text"}


def test_map_sdk_event_other() -> None:
    """Test that other event types return None."""
    # Test non-RunItemStreamEvent
    event = Mock()
    event.type = "other_event_type"
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped is None

    # Test RunItemStreamEvent with unknown item type
    unknown_event = Mock(spec=RunItemStreamEvent)
    unknown_event.type = "run_item_stream_event"
    unknown_event.item = Mock()  # Not a recognized item type
    mapped = map_sdk_event_to_ui_message(unknown_event)
    assert mapped is None


def test_map_sdk_event_wrong_type() -> None:
    """Test event that's not a StreamEvent subtype."""
    # This would raise an error in real usage due to type checking,
    # but we test the runtime behavior
    event = Mock()
    event.type = "unknown"
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped is None
