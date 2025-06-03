"""
Map SDK stream events to our internal agent events.

This module provides a mapping layer between the OpenAI SDK's stream events
and our internal event types, providing a stable interface for the UI.
"""

from dataclasses import dataclass
from typing import Optional, Union

from agents import RunItemStreamEvent, StreamEvent
from agents.items import (  # type: ignore[attr-defined]
    ImageGenerationCall,
    LocalShellCall,
    McpCall,
    MessageOutputItem,
    ReasoningItem,
    ResponseCodeInterpreterToolCall,
    ResponseComputerToolCall,
    ResponseFileSearchToolCall,
    ResponseFunctionToolCall,
    ResponseFunctionWebSearch,
    ToolCallItem,
    ToolCallItemTypes,
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
    match raw_item:
        case ResponseFunctionToolCall(name=name, arguments=arguments):
            return ToolCallEvent(name=name, arguments=arguments)

        case McpCall(name=name, arguments=arguments):
            return ToolCallEvent(name=name, arguments=arguments)

        case LocalShellCall(action=action):
            # LocalShellCall has action with command array
            command_str = " ".join(action.command) if action.command else ""
            return ToolCallEvent(name="shell", arguments=command_str)

        case ResponseComputerToolCall(action=action):
            # Computer tool calls have action instead of name/arguments
            # Convert action to a string representation
            return ToolCallEvent(name="computer", arguments=str(action))

        case ResponseCodeInterpreterToolCall(code=code):
            # Code interpreter has code instead of name/arguments
            return ToolCallEvent(name="code_interpreter", arguments=code)

        case ResponseFileSearchToolCall(queries=queries):
            # File search has queries instead of name/arguments
            # Join queries into a single string
            return ToolCallEvent(name="file_search", arguments=", ".join(queries))

        case ResponseFunctionWebSearch():
            # Web search doesn't have query attribute, just status
            return ToolCallEvent(name="web_search", arguments="")

        case ImageGenerationCall():
            # Image generation doesn't have prompt attribute, just result
            return ToolCallEvent(name="image_generation", arguments="")

        case _:
            # Unknown tool call type
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

                case ReasoningItem(raw_item=raw_item) if raw_item.summary:
                    summary_item = raw_item.summary[0]
                    return ReasoningEvent(text=summary_item.text)

                case MessageOutputItem(raw_item=raw_item) if raw_item.content:
                    content_item = raw_item.content[0]
                    return MessageOutputEvent(text=content_item.text)  # type: ignore[union-attr]

                case _:
                    # Other item types we don't handle
                    return None

        case _:
            # Other StreamEvent types we don't care about
            # (RawResponsesStreamEvent, AgentUpdatedStreamEvent, etc.)
            return None
