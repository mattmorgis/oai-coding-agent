from pathlib import Path

from pytest import MonkeyPatch

import oai_coding_agent.auth.token_storage as token_storage
from oai_coding_agent.auth.token_storage import (
    _read_entries,
    _write_entries,
    delete_token,
    get_auth_file_path,
    get_token,
    has_token,
    save_token,
)


def test_get_auth_file_path_uses_get_config_dir(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    dummy_dir = tmp_path / "cfg_dir"
    monkeypatch.setattr(token_storage, "get_config_dir", lambda: dummy_dir)
    expected = dummy_dir / "auth"
    assert get_auth_file_path() == expected


def test_read_entries_missing_file_returns_empty(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    auth_path = tmp_path / "auth"
    monkeypatch.setattr(token_storage, "get_auth_file_path", lambda: auth_path)
    assert _read_entries() == {}


def test_read_entries_parses_key_value_lines(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    auth_path = tmp_path / "auth"
    monkeypatch.setattr(token_storage, "get_auth_file_path", lambda: auth_path)
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "INVALID_LINE",
            "KEY1=VALUE1",
            "KEY2=VALUE=EXTRA",
            "=NO_KEY",
            "",
        ]
    ) + "\n"
    auth_path.write_text(content)
    entries = _read_entries()
    assert entries == {"KEY1": "VALUE1", "KEY2": "VALUE=EXTRA", "": "NO_KEY"}


def test_write_entries_creates_file_with_content(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    auth_path = tmp_path / "auth"
    monkeypatch.setattr(token_storage, "get_auth_file_path", lambda: auth_path)
    entries = {"A": "1", "B": "2"}
    result = _write_entries(entries)
    assert result is True
    assert auth_path.exists()
    assert auth_path.read_text() == "A=1\nB=2\n"


def test_write_entries_handles_exceptions(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    auth_path = tmp_path / "auth"
    monkeypatch.setattr(token_storage, "get_auth_file_path", lambda: auth_path)

    def fake_write_text(self: Path, data: str, **kwargs: object) -> int:
        raise IOError("fail to write")

    monkeypatch.setattr(Path, "write_text", fake_write_text)
    result = _write_entries({"a": "b"})
    assert result is False


def test_save_get_delete_and_has_token(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    auth_path = tmp_path / "auth"
    monkeypatch.setattr(token_storage, "get_auth_file_path", lambda: auth_path)

    # Save a new token
    assert save_token("key1", "tok1") is True
    assert get_token("key1") == "tok1"
    assert has_token("key1") is True

    # Update existing token
    assert save_token("key1", "newtok") is True
    assert get_token("key1") == "newtok"

    # Add another token
    assert save_token("key2", "tok2") is True
    assert get_token("key2") == "tok2"

    # Delete a token
    assert delete_token("key1") is True
    assert get_token("key1") is None
    assert has_token("key1") is False

    # Ensure other token still exists
    assert has_token("key2") is True

    # Delete non-existent token should succeed silently
    assert delete_token("nope") is True
    assert has_token("nope") is False
