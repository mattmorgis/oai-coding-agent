"""
Map internal agent events to UI messages.
"""

import logging
from typing import Union

from ..agent.events import MessageOutputEvent, ReasoningEvent, ToolCallEvent
from .state import UIMessage

logger = logging.getLogger(__name__)


InternalEvent = Union[ToolCallEvent, ReasoningEvent, MessageOutputEvent]


def map_event_to_ui_message(event: InternalEvent) -> UIMessage:
    """Map an internal agent event to a UI message."""
    logger.debug("Internal event received: %r", event)

    match event:
        case ToolCallEvent(name=name, arguments=arguments):
            return UIMessage(role="tool", content=f"{name}({arguments})")
        case ReasoningEvent(text=text):
            return UIMessage(role="thought", content=f"💭 {text}")
        case MessageOutputEvent(text=text):
            return UIMessage(role="assistant", content=text)
