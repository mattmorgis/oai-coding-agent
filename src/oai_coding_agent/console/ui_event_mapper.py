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

    if not isinstance(event, AgentRunItemStreamEvent):
        return None

    item = event.item

    if isinstance(item, AgentToolCallItem):
        raw = item.raw_item
        return UIMessage(role="tool", content=f"{raw.name}({raw.arguments})")

    if isinstance(item, AgentReasoningItem) and item.raw_item.summary:
        raw = item.raw_item
        return UIMessage(role="thought", content=f"💭 {raw.summary[0].text}")

    if isinstance(item, AgentMessageOutputItem) and item.raw_item.content:
        raw = item.raw_item
        return UIMessage(role="assistant", content=raw.content[0].text)

    return None
