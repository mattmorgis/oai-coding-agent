"""
Map SDK events to UI messages.
"""

import logging
from typing import Any, Optional

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
            raw_any: Any = raw
            return UIMessage(role="tool", content=f"{raw_any.name}({raw_any.arguments})")
        case AgentRunItemStreamEvent(item=AgentReasoningItem(raw_item=raw)) if raw.summary:
            raw_any: Any = raw
            return UIMessage(role="thought", content=f"💭 {raw_any.summary[0].text}")
        case AgentRunItemStreamEvent(item=AgentMessageOutputItem(raw_item=raw)) if raw.content:
            raw_any: Any = raw
            return UIMessage(role="assistant", content=raw_any.content[0].text)
        case _:
            return None
