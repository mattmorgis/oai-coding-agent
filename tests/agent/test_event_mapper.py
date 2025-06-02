"""Tests for event_mapper module."""

from typing import Any

from oai_coding_agent.agent.event_mapper import map_sdk_event_to_ui_message


class DummyRaw:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class DummyItem:
    def __init__(self, raw_item: Any) -> None:
        self.raw_item = raw_item


class DummyEvent:
    def __init__(self, type: Any = None, name: Any = None, item: Any = None) -> None:
        self.type = type
        self.name = name
        self.item = item


def test_map_sdk_event_tool_called() -> None:
    """Test mapping of tool_called events."""
    raw = DummyRaw(name="cmd", arguments=("a", "b"))
    event = DummyEvent(
        type="run_item_stream_event", name="tool_called", item=DummyItem(raw)
    )
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped == {"role": "tool", "content": "cmd(('a', 'b'))"}


def test_map_sdk_event_reasoning_with_summary() -> None:
    """Test mapping of reasoning events with summary."""
    raw = DummyRaw(summary=[DummyRaw(text="thinking")])
    event = DummyEvent(name="reasoning_item_created", item=DummyItem(raw))
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped == {"role": "thought", "content": "💭 thinking"}


def test_map_sdk_event_reasoning_without_summary() -> None:
    """Test mapping of reasoning events without summary."""
    raw = DummyRaw(summary=[])
    event = DummyEvent(name="reasoning_item_created", item=DummyItem(raw))
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped is None


def test_map_sdk_event_reasoning_with_empty_summary() -> None:
    """Test mapping of reasoning events with None summary."""
    raw = DummyRaw(summary=None)
    event = DummyEvent(name="reasoning_item_created", item=DummyItem(raw))
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped is None


def test_map_sdk_event_message_output_created() -> None:
    """Test mapping of message output events."""
    raw = DummyRaw(content=[DummyRaw(text="output text")])
    event = DummyEvent(name="message_output_created", item=DummyItem(raw))
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped == {"role": "assistant", "content": "output text"}


def test_map_sdk_event_other() -> None:
    """Test that other event types return None."""
    event = DummyEvent(type="other", name="something_else", item=DummyItem(DummyRaw()))
    mapped = map_sdk_event_to_ui_message(event)
    assert mapped is None


def test_map_sdk_event_no_attributes() -> None:
    """Test event with no type or name attributes."""

    class EmptyEvent:
        pass

    mapped = map_sdk_event_to_ui_message(EmptyEvent())
    assert mapped is None
