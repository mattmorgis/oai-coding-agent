"""
Map SDK stream events to our internal agent events.

This module provides a mapping layer between the OpenAI SDK's stream events
and our internal event types, providing a stable interface for the UI.
"""

from dataclasses import dataclass
from typing import Optional, Union

from agents import RunItemStreamEvent, StreamEvent
from agents.items import (
    MessageOutputItem,
    ReasoningItem,
    ToolCallItem,
    ToolCallItemTypes,
)
from openai.types.responses import (
    ResponseOutputMessage,
    ResponseReasoningItem,
)


# Internal agent event types
@dataclass
class ToolCallEvent:
    """A tool call event with well-defined types."""

    name: str
    arguments: str


@dataclass
class ReasoningEvent:
    """A reasoning event with well-defined types."""

    text: str


@dataclass
class MessageOutputEvent:
    """A message output event with well-defined types."""

    text: str


# Union type for all agent events
AgentEvent = Union[ToolCallEvent, ReasoningEvent, MessageOutputEvent]


def _extract_tool_call_info(raw_item: ToolCallItemTypes) -> Optional[ToolCallEvent]:
    """Extract name and arguments from a tool call item."""
    # Most tool call types have direct name/arguments attributes
    if hasattr(raw_item, "name") and hasattr(raw_item, "arguments"):
        return ToolCallEvent(name=raw_item.name, arguments=raw_item.arguments)

    # Some types might nest them under a function attribute
    if hasattr(raw_item, "function"):
        func = raw_item.function
        if hasattr(func, "name") and hasattr(func, "arguments"):
            return ToolCallEvent(name=func.name, arguments=func.arguments)

    return None


def _extract_reasoning_text(
    raw_item: ResponseReasoningItem,
) -> Optional[ReasoningEvent]:
    """Extract text from a reasoning item."""
    if raw_item.summary and len(raw_item.summary) > 0:
        summary_item = raw_item.summary[0]
        if hasattr(summary_item, "text"):
            return ReasoningEvent(text=summary_item.text)
    return None


def _extract_message_text(
    raw_item: ResponseOutputMessage,
) -> Optional[MessageOutputEvent]:
    """Extract text from a message output item."""
    if raw_item.content and len(raw_item.content) > 0:
        content_item = raw_item.content[0]
        if hasattr(content_item, "text"):
            return MessageOutputEvent(text=content_item.text)
    return None


def map_sdk_event_to_agent_event(
    sdk_event: StreamEvent,
) -> Optional[AgentEvent]:
    """Map SDK stream events to our internal agent event types.

    Args:
        sdk_event: A stream event from the OpenAI SDK. StreamEvent is a union type
                   that includes RunItemStreamEvent, RawResponsesStreamEvent, and
                   AgentUpdatedStreamEvent. We only care about RunItemStreamEvent
                   which contains the actual items (tool calls, messages, etc.)

    Returns:
        An internal agent event (ToolCallEvent, ReasoningEvent, or MessageOutputEvent),
        or None if the SDK event cannot be mapped
    """
    match sdk_event:
        case RunItemStreamEvent(item=item):
            # Process the item within RunItemStreamEvent
            match item:
                case ToolCallItem(raw_item=raw_item):
                    return _extract_tool_call_info(raw_item)

                case ReasoningItem(raw_item=raw_item):
                    return _extract_reasoning_text(raw_item)

                case MessageOutputItem(raw_item=raw_item):
                    return _extract_message_text(raw_item)

                case _:
                    # Other item types we don't handle
                    return None

        case _:
            # Other StreamEvent types we don't care about
            # (RawResponsesStreamEvent, AgentUpdatedStreamEvent, etc.)
            return None
