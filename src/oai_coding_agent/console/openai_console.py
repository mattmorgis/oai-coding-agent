from typing import Optional

import typer
from rich.prompt import Confirm

from oai_coding_agent.auth.token_storage import get_token, save_token

_OPENAI_KEY = "OPENAI_API_KEY"


class OpenAIConsole:
    """Console flow to prompt for—and store—the OpenAI API key."""

    def __init__(self) -> None:
        pass

    def prompt_auth(
        self, force: bool = False, new_key: Optional[str] = None
    ) -> Optional[str]:
        """
        If OPENAI_API_KEY already stored, return it (unless force=True, in
        which case ask before overwriting).
        Otherwise prompt the user (hidden input) and save it.
        """
        existing = get_token(_OPENAI_KEY)
        if existing and not force:
            return existing

        if existing and force:
            if not Confirm.ask("An OpenAI API key is already configured; overwrite?"):
                return existing

        if new_key is not None:
            key = new_key
        else:
            key = typer.prompt("OpenAI API key", hide_input=True)
        if key:
            save_token(_OPENAI_KEY, key)
        return key

    def check_or_authenticate(
        self, force: bool = False, new_key: Optional[str] = None
    ) -> Optional[str]:
        """Alias for prompt_auth to match GitHubConsole API."""
        return self.prompt_auth(force, new_key)
