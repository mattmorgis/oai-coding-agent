"""
Map agent events to UI messages.
"""

import logging
from typing import TypedDict

from ..agent.events import AgentEvent, MessageOutputEvent, ReasoningEvent, ToolCallEvent

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
        case ReasoningEvent(text=text):
            return UIMessage(role="thought", content=f"{text}")
        case MessageOutputEvent(text=text):
            return UIMessage(role="assistant", content=text)
