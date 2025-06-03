"""Tests for the events module."""

from unittest.mock import Mock

from agents import RunItemStreamEvent
from agents.items import (
    MessageOutputItem,
    ReasoningItem,
    ResponseFunctionToolCall,
    ToolCallItem,
)

from oai_coding_agent.agent.events import (
    MessageOutputEvent,
    ReasoningEvent,
    ToolCallEvent,
    map_sdk_event_to_agent_event,
)


def test_map_tool_call_with_response_function_tool_call() -> None:
    """Test mapping a ResponseFunctionToolCall using the typed branch."""
    rf = ResponseFunctionToolCall(
        name="test_tool",
        arguments='{"arg": "value"}',
        call_id="cid",
        type="function_call",
    )
    tool_call_item = ToolCallItem(agent=Mock(), raw_item=rf)

    event = Mock(spec=RunItemStreamEvent)
    event.item = tool_call_item

    result = map_sdk_event_to_agent_event(event)

    assert isinstance(result, ToolCallEvent)
    assert result.name == "test_tool"
    assert result.arguments == '{"arg": "value"}'


def test_map_reasoning_event() -> None:
    """Test mapping reasoning event with summary text."""
    reasoning_item = Mock(spec=ReasoningItem)
    reasoning_raw = Mock()
    reasoning_raw.summary = [Mock(text="Test reasoning text")]
    reasoning_item.raw_item = reasoning_raw

    event = Mock(spec=RunItemStreamEvent)
    event.item = reasoning_item

    result = map_sdk_event_to_agent_event(event)

    assert isinstance(result, ReasoningEvent)
    assert result.text == "Test reasoning text"


def test_map_message_output_event() -> None:
    """Test mapping message output event with content text."""
    message_item = Mock(spec=MessageOutputItem)
    message_raw = Mock()
    message_raw.content = [Mock(text="Test message content")]
    message_item.raw_item = message_raw

    event = Mock(spec=RunItemStreamEvent)
    event.item = message_item

    result = map_sdk_event_to_agent_event(event)

    assert isinstance(result, MessageOutputEvent)
    assert result.text == "Test message content"


def test_map_invalid_tool_call_returns_none() -> None:
    """Test that tool call without required attributes returns None."""
    tool_call_item = Mock(spec=ToolCallItem)
    tool_call_raw = Mock()
    # No name or arguments attributes
    del tool_call_raw.name
    del tool_call_raw.arguments
    del tool_call_raw.function
    tool_call_item.raw_item = tool_call_raw

    event = Mock(spec=RunItemStreamEvent)
    event.item = tool_call_item

    result = map_sdk_event_to_agent_event(event)

    assert result is None


def test_map_empty_reasoning_returns_none() -> None:
    """Test that reasoning event with empty summary returns None."""
    reasoning_item = Mock(spec=ReasoningItem)
    reasoning_raw = Mock()
    reasoning_raw.summary = []  # Empty summary
    reasoning_item.raw_item = reasoning_raw

    event = Mock(spec=RunItemStreamEvent)
    event.item = reasoning_item

    result = map_sdk_event_to_agent_event(event)

    assert result is None


def test_map_empty_message_content_returns_none() -> None:
    """Test that message event with empty content returns None."""
    message_item = Mock(spec=MessageOutputItem)
    message_raw = Mock()
    message_raw.content = []  # Empty content
    message_item.raw_item = message_raw

    event = Mock(spec=RunItemStreamEvent)
    event.item = message_item

    result = map_sdk_event_to_agent_event(event)

    assert result is None


def test_map_non_run_item_event_returns_none() -> None:
    """Test that non-RunItemStreamEvent returns None."""
    event = Mock()  # Not a RunItemStreamEvent

    result = map_sdk_event_to_agent_event(event)

    assert result is None


def test_map_unknown_item_type_returns_none() -> None:
    """Test that unknown item type returns None."""
    unknown_item = Mock()  # Not a recognized item type
    unknown_item.raw_item = Mock()

    event = Mock(spec=RunItemStreamEvent)
    event.item = unknown_item

    result = map_sdk_event_to_agent_event(event)

    assert result is None
