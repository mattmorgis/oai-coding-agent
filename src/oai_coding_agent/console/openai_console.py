from typing import Optional

from rich.prompt import Confirm, Prompt

from oai_coding_agent.auth.token_storage import get_token, save_token

_OPENAI_KEY = "OPENAI_API_KEY"


class OpenAIConsole:
    """Console flow to prompt for—and store—the OpenAI API key."""

    def __init__(self) -> None:
        pass

    def prompt_auth(self) -> Optional[str]:
        """Prompt for OpenAI API key if not already stored (hidden input) and save it."""
        existing = get_token(_OPENAI_KEY)
        if existing:
            return existing

        key = Prompt.ask("OpenAI API key", password=True)
        if key:
            save_token(_OPENAI_KEY, key)
        return key

    def check_or_authenticate(self) -> Optional[str]:
        """Check for existing key and optionally overwrite, or prompt if missing."""
        existing = get_token(_OPENAI_KEY)
        if existing:
            if Confirm.ask("An OpenAI API key is already configured; overwrite?"):
                key = Prompt.ask("OpenAI API key", password=True)
                if key:
                    save_token(_OPENAI_KEY, key)
                return key
            return existing
        return self.prompt_auth()
