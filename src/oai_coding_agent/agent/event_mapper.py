"""
Map SDK events to UI messages.
"""

import logging
from typing import Any, Optional

from ..console.state import UIMessage

logger = logging.getLogger(__name__)


def map_sdk_event_to_ui_message(event: Any) -> Optional[UIMessage]:
    """Map an SDK event to a UI message."""
    evt_type = getattr(event, "type", None)
    evt_name = getattr(event, "name", None)
    logger.debug(
        "SDK event received: type=%s, name=%s, event=%r", evt_type, evt_name, event
    )

    if evt_type == "run_item_stream_event" and evt_name == "tool_called":
        return {
            "role": "tool",
            "content": f"{event.item.raw_item.name}({event.item.raw_item.arguments})",
        }
    if evt_name == "reasoning_item_created":
        summary = event.item.raw_item.summary
        if summary:
            text = summary[0].text
            return {"role": "thought", "content": f"💭 {text}"}
    if evt_name == "message_output_created":
        return {
            "role": "assistant",
            "content": event.item.raw_item.content[0].text,
        }
    return None
