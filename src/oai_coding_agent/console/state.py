"""
UI state container (replaces global messages and slash_commands).
"""

from typing import Callable, Dict, List


class UIState:
    """Holds messages and registered slash commands for the console interface."""

    def __init__(self) -> None:
        self.messages: List[dict] = []
        self.slash_commands: Dict[str, Callable[..., bool]] = {}
