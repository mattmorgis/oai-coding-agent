from pathlib import Path
from typing import Generator

import pytest
from rich.prompt import Confirm, Prompt

from oai_coding_agent.auth.token_storage import (
    get_auth_file_path,
    get_token,
    save_token,
)
from oai_coding_agent.console.openai_console import OpenAIConsole

dir_path = Path(__file__).parent
test_key = "OPENAI_API_KEY"


@pytest.fixture(autouse=True)
def isolate_xdg_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Generator[None, None, None]:
    # Ensure we use a temp XDG_CONFIG_HOME so we don't touch real config
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # Remove any existing file
    auth_file = get_auth_file_path()
    if auth_file.exists():
        auth_file.unlink()
    yield


def test_prompt_auth_creates_and_returns_new_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No existing token; should prompt once and save
    console = OpenAIConsole()
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "newkey123")

    key = console.prompt_auth()
    assert key == "newkey123"

    # File should exist and contain the saved key
    content = get_token(test_key)
    assert content == "newkey123"


def test_prompt_auth_returns_existing_without_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pre-write a token
    save_token(test_key, "existingkey")

    console = OpenAIConsole()
    # If prompt called, fail
    monkeypatch.setattr(
        Prompt,
        "ask",
        lambda *args, **kwargs: pytest.fail("Prompt should not be called"),
    )

    key = console.prompt_auth()
    assert key == "existingkey"


def test_check_or_authenticate_prompts_if_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No existing token, should prompt and save
    console = OpenAIConsole()
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "freshkey")

    key = console.check_or_authenticate()
    assert key == "freshkey"
    assert get_token(test_key) == "freshkey"


def test_check_or_authenticate_overwrite_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_token(test_key, "oldkey")
    console = OpenAIConsole()
    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: True)
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "newkey")

    key = console.check_or_authenticate()
    assert key == "newkey"
    assert get_token(test_key) == "newkey"


def test_check_or_authenticate_overwrite_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_token(test_key, "keepkey")
    console = OpenAIConsole()
    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        Prompt,
        "ask",
        lambda *args, **kwargs: pytest.fail("Prompt should not be called"),
    )

    key = console.check_or_authenticate()
    assert key == "keepkey"
    assert get_token(test_key) == "keepkey"
