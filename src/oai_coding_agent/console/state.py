"""
UI state container (replaces global messages and slash_commands).
"""

from typing import Callable, Dict, TypedDict


class UIMessage(TypedDict):
    role: str
    content: str


class UIState:
    """Holds registered slash commands for the console interface."""

    def __init__(self) -> None:
        self.slash_commands: Dict[str, Callable[..., bool]] = {}
