"""
Map SDK events to UI messages.
"""

import logging
from typing import Any, Optional

from agents import RunItemStreamEvent
from ..agent.events import AgentEvent
from agents.items import MessageOutputItem, ReasoningItem, ToolCallItem

from .state import UIMessage

logger = logging.getLogger(__name__)


def map_sdk_event_to_ui_message(event: AgentEvent) -> Optional[UIMessage]:
    """Map an SDK event to a UI message."""
    logger.debug("SDK event received: type=%s, event=%r", event.type, event)

    if isinstance(event, RunItemStreamEvent):
        item = event.item

        # Type-based dispatch using the actual item types
        if isinstance(item, ToolCallItem):
            # For tool calls, we need to handle the union type of raw_item
            tool_raw: Any = item.raw_item
            if hasattr(tool_raw, "name") and hasattr(tool_raw, "arguments"):
                return {
                    "role": "tool",
                    "content": f"{tool_raw.name}({tool_raw.arguments})",
                }
        elif isinstance(item, ReasoningItem):
            # For reasoning items, check if summary exists
            reasoning_raw: Any = item.raw_item
            if hasattr(reasoning_raw, "summary") and reasoning_raw.summary:
                text = reasoning_raw.summary[0].text
                return {"role": "thought", "content": f"💭 {text}"}
        elif isinstance(item, MessageOutputItem):
            # For message output, get the content
            msg_raw: Any = item.raw_item
            if (
                hasattr(msg_raw, "content")
                and msg_raw.content
                and len(msg_raw.content) > 0
            ):
                content_item = msg_raw.content[0]
                if hasattr(content_item, "text"):
                    return {
                        "role": "assistant",
                        "content": content_item.text,
                    }

    return None
