import stat
from pathlib import Path
from unittest.mock import MagicMock

import git
import pytest

from oai_coding_agent.preflight.commit_hook import (
    COMMIT_MSG_HOOK_SCRIPT,
    install_commit_msg_hook,
)


def test_install_commit_msg_hook_creates_hook_and_configures_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    install_commit_msg_hook should write the commit-msg hook from the template,
    make it executable, and call git config to set core.hooksPath.
    """
    # Point XDG_DATA_HOME to a temporary location
    data_home = tmp_path / "data_home"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    # Create a fake repo directory
    repo = tmp_path / "repo"
    repo.mkdir()

    # Mock GitPython
    mock_repo = MagicMock()
    mock_config_writer = MagicMock()

    # Track calls to set_value
    set_value_calls = []

    def track_set_value(section: str, option: str, value: str) -> MagicMock:
        set_value_calls.append((section, option, value))
        return mock_config_writer

    mock_config_writer.set_value = track_set_value
    mock_config_writer.release = MagicMock()
    mock_repo.config_writer = MagicMock(return_value=mock_config_writer)

    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)

    # Run the installer
    install_commit_msg_hook(repo)

    # Check that the hook file was created in the XDG_DATA_HOME path
    hooks_dir = data_home / "oai_coding_agent" / "hooks"
    hook_file = hooks_dir / "commit-msg"
    assert hook_file.exists(), "Expected commit-msg hook file to be created"

    # Verify the content matches the expected script
    actual_script = hook_file.read_text(encoding="utf-8")
    assert actual_script == COMMIT_MSG_HOOK_SCRIPT

    # Verify file is executable (user executable bit should be set)
    mode = stat.S_IMODE(hook_file.stat().st_mode)
    assert mode & stat.S_IXUSR, "Expected commit-msg hook to be executable"

    # Verify GitPython config was called to set core.hooksPath
    assert len(set_value_calls) == 1
    section, option, value = set_value_calls[0]
    assert section == "core"
    assert option == "hooksPath"
    assert value == str(hooks_dir)

    # Verify release was called
    mock_config_writer.release.assert_called_once()
