"""
UI state container (replaces global messages and slash_commands).
"""

from typing import Callable, Dict, List, Optional

from prompt_toolkit import PromptSession


class UIState:
    """Holds messages and registered slash commands for the console interface."""

    def __init__(self) -> None:
        self.messages: List[dict] = []
        self.slash_commands: Dict[str, Callable[..., bool]] = {}
        # Configuration options toggled via /config
        self.config: Dict[str, bool] = {"vim_mode": False}
        # PromptSession instance for runtime config changes
        self.prompt_session: Optional[PromptSession] = None
