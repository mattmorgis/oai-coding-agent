"""
Map SDK events to UI messages.
"""

import logging
from typing import Optional

from ..agent.events import (
    AgentEvent,
    AgentRunItemStreamEvent,
    AgentToolCallItem,
    AgentReasoningItem,
    AgentMessageOutputItem,
)

from .state import UIMessage

logger = logging.getLogger(__name__)


def map_sdk_event_to_ui_message(event: AgentEvent) -> Optional[UIMessage]:
    """Map an SDK event to a UI message."""
    logger.debug("SDK event received: type=%s, event=%r", event.type, event)

    # Uses Python 3.10 structural pattern-matching for clearer dispatch
    match event:
        case AgentRunItemStreamEvent(item=AgentToolCallItem(raw_item=raw)):
            return UIMessage(role="tool", content=f"{raw.name}({raw.arguments})")
        case AgentRunItemStreamEvent(item=AgentReasoningItem(raw_item=raw)) if raw.summary:
            return UIMessage(role="thought", content=f"💭 {raw.summary[0].text}")
        case AgentRunItemStreamEvent(item=AgentMessageOutputItem(raw_item=raw)) if raw.content:
            return UIMessage(role="assistant", content=raw.content[0].text)
        case _:
            return None
