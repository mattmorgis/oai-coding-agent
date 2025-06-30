from pathlib import Path
from stat import S_IMODE

import pytest

import oai_coding_agent.auth.token_storage as token_storage


def test_get_auth_file_path_uses_xdg_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ensure get_auth_file_path uses XDG_CONFIG_HOME environment variable
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    expected = tmp_path / "oai_coding_agent" / "auth"
    assert token_storage.get_auth_file_path() == expected


def test_read_entries_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # _read_entries should return empty dict when auth file does not exist
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert token_storage._read_entries() == {}


def test_write_and_read_empty_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # _write_entries should write a newline for empty entries and _read_entries should return {}
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert token_storage._write_entries({}) is True
    auth_file = token_storage.get_auth_file_path()
    assert auth_file.read_text() == "\n"
    assert token_storage._read_entries() == {}


def test_write_and_read_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # _write_entries should persist key=value entries and _read_entries should retrieve them
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    entries_in = {"key1": "value1", "key2": "value2"}
    assert token_storage._write_entries(entries_in) is True
    auth_file = token_storage.get_auth_file_path()
    # verify file permissions are secure (rw-------)
    mode = S_IMODE(auth_file.stat().st_mode)
    assert mode == 0o600
    # verify contents and parsed entries
    assert token_storage._read_entries() == entries_in


def test_save_get_delete_has_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Test high-level token operations: save_token, get_token, has_token, delete_token
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert not token_storage.has_token("foo")
    assert token_storage.get_token("foo") is None

    # Save a token and verify retrieval
    assert token_storage.save_token("foo", "bar") is True
    assert token_storage.get_token("foo") == "bar"
    assert token_storage.has_token("foo") is True

    # Save another token and ensure both exist
    assert token_storage.save_token("baz", "qux") is True
    assert token_storage.get_token("baz") == "qux"

    # Delete a token and ensure it's removed
    assert token_storage.delete_token("foo") is True
    assert token_storage.get_token("foo") is None
    assert not token_storage.has_token("foo")

    # Deleting a non-existent key should still succeed and not affect other tokens
    assert token_storage.delete_token("non-existent") is True
    assert token_storage.get_token("baz") == "qux"


def test_write_entries_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate a failure in writing to the auth file
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    def fake_write_text(self: Path, content: str) -> None:
        raise OSError("write failed")

    monkeypatch.setattr(Path, "write_text", fake_write_text)
    # save_token should return False on write failure
    assert token_storage.save_token("a", "b") is False
    # delete_token should also return False when write fails
    assert token_storage.delete_token("a") is False
