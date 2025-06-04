"""Unit tests for preflight utility functions."""

import os
import stat
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import git
import pytest

from oai_coding_agent.preflight import get_tool_version, install_commit_msg_hook


def test_get_tool_version_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_tool_version returns stdout.strip() on success"""
    fake_cp = subprocess.CompletedProcess(
        ["foo", "--version"], 0, stdout="v1.2.3\n", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: fake_cp)
    assert get_tool_version(["foo", "--version"]) == "v1.2.3"


def test_get_tool_version_file_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_tool_version raises RuntimeError for FileNotFoundError"""

    def fake_run(*args: Any, **kwargs: Any) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError) as exc:
        get_tool_version(["foo", "--version"])
    assert "'foo' binary not found on PATH" in str(exc.value)


def test_get_tool_version_called_process_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_tool_version raises RuntimeError for CalledProcessError"""

    def fake_run(*args: Any, **kwargs: Any) -> None:
        raise subprocess.CalledProcessError(
            returncode=1, cmd=["foo", "--version"], stderr="error"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError) as exc:
        get_tool_version(["foo", "--version"])
    assert "Failed to run 'foo --version'" in str(exc.value)


def test_install_commit_msg_hook_creates_and_configures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """install_commit_msg_hook writes hook file and configures git core.hooksPath"""
    # Point XDG_CONFIG_HOME to a temporary dir
    config_home = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    # Prepare a fake git.Repo and config_writer
    fake_repo = MagicMock()
    fake_writer = MagicMock()
    fake_writer.set_value.return_value = fake_writer
    fake_writer.release.return_value = None
    fake_repo.config_writer.return_value = fake_writer
    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: fake_repo)

    # Run the hook installation
    install_commit_msg_hook(Path("ignored_repo"))

    hooks_dir = config_home / "oai_coding_agent" / "hooks"
    hook_file = hooks_dir / "commit-msg"

    # The hook file should exist and contain the expected stanza
    assert hook_file.exists(), "commit-msg hook file was not created"
    content = hook_file.read_text(encoding="utf-8")
    assert "Generated with oai-coding-agent" in content

    # The hook file should be executable
    assert hook_file.stat().st_mode & stat.S_IXUSR, "Hook file is not executable"

    # Git config should have been updated
    fake_repo.config_writer.assert_called_once()
    fake_writer.set_value.assert_called_once_with("core", "hooksPath", str(hooks_dir))
    fake_writer.release.assert_called_once()


def test_install_commit_msg_hook_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """install_commit_msg_hook does not rewrite hook if content is unchanged"""
    config_home = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    fake_repo = MagicMock()
    fake_writer = MagicMock()
    fake_writer.set_value.return_value = fake_writer
    fake_writer.release.return_value = None
    fake_repo.config_writer.return_value = fake_writer
    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: fake_repo)

    # First run: create the hook
    install_commit_msg_hook(Path("ignored"))
    hook_path = config_home / "oai_coding_agent" / "hooks" / "commit-msg"
    mtime1 = hook_path.stat().st_mtime

    # Second run: should not touch the file
    install_commit_msg_hook(Path("ignored"))
    mtime2 = hook_path.stat().st_mtime

    assert mtime1 == mtime2, (
        "Hook file was rewritten even though content did not change"
    )
