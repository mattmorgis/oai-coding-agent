"""
UI state container (replaces global messages and slash_commands).
"""

from typing import Callable, Dict, List, TypedDict


class Message(TypedDict):
    """Simple message container used by the UI state."""

    role: str
    content: str


class UIState:
    """Holds messages and registered slash commands for the console interface."""

    def __init__(self) -> None:
        self.messages: List[Message] = []
        self.slash_commands: Dict[str, Callable[..., bool]] = {}
