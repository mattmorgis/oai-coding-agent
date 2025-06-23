"""
Map agent events to UI messages.
"""

import logging
from typing import TypedDict

from ..agent.events import (
    AgentEvent,
    ErrorEvent,
    MessageOutputEvent,
    ReasoningEvent,
    ToolCallEvent,
    ToolCallOutputEvent,
)

logger = logging.getLogger(__name__)


class UIMessage(TypedDict):
    role: str
    content: str


def map_event_to_ui_message(event: AgentEvent) -> UIMessage:
    """Map an agent event to a UI message."""
    logger.debug("Internal event received: %r", event)

    match event:
        case ToolCallEvent(name=name, arguments=arguments):
            return UIMessage(role="tool", content=f"{name}({arguments})")
        case ToolCallOutputEvent(output=output):
            return UIMessage(role="tool", content=f"{output}")
        case ReasoningEvent(text=text):
            return UIMessage(role="thought", content=f"{text}")
        case MessageOutputEvent(text=text):
            return UIMessage(role="assistant", content=text)
        case ErrorEvent(message=msg):
            return UIMessage(role="error", content=msg)
        case _:
            logger.warning("Unhandled AgentEvent in UI mapping: %r", event)
            return UIMessage(role="assistant", content="")
