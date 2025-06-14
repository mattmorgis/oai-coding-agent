from pathlib import Path

import pytest

from oai_coding_agent.github.token_storage import (
    delete_github_token,
    get_auth_file_path,
    get_github_token,
    has_stored_token,
    save_github_token,
)


def test_get_auth_file_path_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No XDG_DATA_HOME, use HOME for fallback
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    expected = home_dir / ".local" / "share" / "oai_coding_agent" / "auth"
    assert get_auth_file_path() == expected


def test_get_auth_file_path_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Use XDG_DATA_HOME override
    xdg_data = tmp_path / "xdg_data"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))

    expected = xdg_data / "oai_coding_agent" / "auth"
    assert get_auth_file_path() == expected


def test_save_get_delete_token_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Use XDG_DATA_HOME override to avoid touching real user directories
    xdg_data = tmp_path / "xdg_data"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))

    # Ensure clean state
    delete_github_token()
    assert get_github_token() is None
    assert not has_stored_token()

    # Save a token
    token = "test-token"
    assert save_github_token(token) is True
    auth_file = get_auth_file_path()
    assert auth_file.exists()
    assert auth_file.read_text() == f"GITHUB_TOKEN={token}\n"

    # Token exists
    assert has_stored_token() is True
    assert get_github_token() == token

    # Delete token
    assert delete_github_token() is True
    assert not auth_file.exists()
    assert has_stored_token() is False
    assert get_github_token() is None
