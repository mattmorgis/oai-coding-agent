"""
Map SDK stream events to our internal agent events.

This module provides a mapping layer between the OpenAI SDK's stream events
and our internal agent event types, providing a stable interface for the UI.
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
    ToolCallOutputItem,
)
from agents.stream_events import RawResponsesStreamEvent
from openai.types.responses import ResponseCompletedEvent


# Internal agent event types
@dataclass
class ToolCallEvent:
    """A tool call event with well-defined types."""

    name: str
    arguments: str
    call_id: Optional[str] = None


@dataclass
class ReasoningEvent:
    """A reasoning event with well-defined types."""

    text: str


@dataclass
class MessageOutputEvent:
    """A message output event with well-defined types."""

    text: str


# Internal agent event types
@dataclass
class ErrorEvent:
    """An error event emitted by the agent (e.g. MaxTurnsExceeded)."""

    message: str


@dataclass
class ToolCallOutputEvent:
    """The output side of a tool call (e.g. function call result)."""

    call_id: str
    output: str


@dataclass
class UsageEvent:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int
    total_tokens: int

    def __add__(self, other: "UsageEvent") -> "UsageEvent":
        """Add two UsageEvent objects by summing their token counts."""
        if not isinstance(other, UsageEvent):
            return NotImplemented
        return UsageEvent(
            input_tokens=self.input_tokens + other.input_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reasoning_output_tokens=self.reasoning_output_tokens
            + other.reasoning_output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


# Union type for all agent events
AgentEvent = Union[
    ToolCallEvent,
    ReasoningEvent,
    MessageOutputEvent,
    ErrorEvent,
    ToolCallOutputEvent,
    UsageEvent,
]


def _extract_tool_call_info(raw_item: ToolCallItemTypes) -> Optional[ToolCallEvent]:
    """Extract name and arguments from a tool call item."""
    match raw_item:
        case ResponseFunctionToolCall(name=name, arguments=arguments, call_id=call_id):
            return ToolCallEvent(name=name, arguments=arguments, call_id=call_id)

        case McpCall(id=id, name=name, arguments=arguments):
            return ToolCallEvent(name=name, arguments=arguments, call_id=id)

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

                case ToolCallOutputItem(
                    raw_item={
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": output,
                    }
                ) if isinstance(call_id, str) and isinstance(output, str):
                    return ToolCallOutputEvent(call_id=call_id, output=output)

                case ReasoningItem(raw_item=raw_item) if raw_item.summary:
                    # Concatenate all summary items
                    summary_texts = [item.text for item in raw_item.summary]
                    combined_text = "\n\n".join(summary_texts)
                    return ReasoningEvent(text=combined_text)

                case MessageOutputItem(raw_item=raw_item) if raw_item.content:
                    # Concatenate all content items
                    content_texts = [item.text for item in raw_item.content]  # type: ignore[union-attr]
                    combined_text = "\n\n".join(content_texts)
                    return MessageOutputEvent(text=combined_text)

                case _:
                    # Other item types we don't handle
                    return None

        case RawResponsesStreamEvent(data=resp_ev) if isinstance(
            resp_ev, ResponseCompletedEvent
        ):
            usage = resp_ev.response.usage
            if usage is None:
                return None
            return UsageEvent(
                input_tokens=usage.input_tokens,
                cached_input_tokens=usage.input_tokens_details.cached_tokens,
                output_tokens=usage.output_tokens,
                reasoning_output_tokens=usage.output_tokens_details.reasoning_tokens,
                total_tokens=usage.total_tokens,
            )
        case _:
            # Other StreamEvent types we don't care about
            return None
