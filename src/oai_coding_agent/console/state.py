"""
UI state container (replaces global messages and slash_commands).
"""

import asyncio
from typing import Any, Callable, Dict, Optional, TypedDict, TypeVar

T = TypeVar("T")


class UIMessage(TypedDict):
    role: str
    content: str


class UIState:
    """Store user interface state information."""

    def __init__(self) -> None:
        """Initialize UI state."""
        self.slash_commands: Dict[str, Callable[..., bool]] = {}
        self.current_stream_task: Optional[asyncio.Task[Any]] = None
        self.current_result: Optional[Any] = None
        self.last_completed_response_id: Optional[str] = None
        self.interrupted: bool = False

    def set_running_task(
        self,
        stream_task: Optional[asyncio.Task[Any]],
        result: Optional[Any],
        last_response_id: Optional[str] = None,
    ) -> None:
        """Set the currently running task and result for potential cancellation.

        Args:
            stream_task: The asyncio task consuming the event stream
            result: The result object from agent.run()
            last_response_id: The last completed response ID for state restoration
        """
        self.current_stream_task = stream_task
        self.current_result = result
        self.last_completed_response_id = last_response_id
        self.interrupted = False

    def cancel_current_task(self) -> None:
        """Cancel the currently running task and result."""
        if self.current_stream_task:
            if not self.current_stream_task.done():
                self.current_stream_task.cancel()

        if self.current_result:
            self.current_result.cancel()
