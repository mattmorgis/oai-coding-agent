import stat
import subprocess
from pathlib import Path

import pytest
from jinja2 import Environment, PackageLoader, select_autoescape

from oai_coding_agent.preflight import install_commit_msg_hook


def test_install_commit_msg_hook_creates_hook_and_configures_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    install_commit_msg_hook should write the commit-msg hook from the template,
    make it executable, and call git config to set core.hooksPath.
    """
    # Point XDG_CONFIG_HOME to a temporary location
    config_home = tmp_path / "config_home"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    # Create a fake repo directory
    repo = tmp_path / "repo"
    repo.mkdir()

    # Capture subprocess.run calls
    runs = []

    def fake_run(
        cmd: list[str],
        cwd: Path | None = None,
        check: bool = False,
    ) -> None:
        runs.append((cmd, cwd, check))

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Run the installer
    install_commit_msg_hook(repo)

    # Check that the hook file was created in the XDG_CONFIG_HOME path
    hooks_dir = config_home / "oai-coding-agent" / "hooks"
    hook_file = hooks_dir / "commit-msg"
    assert hook_file.exists(), "Expected commit-msg hook file to be created"

    # Verify the content matches the Jinja2 template rendering
    env = Environment(
        loader=PackageLoader("oai_coding_agent", "templates"),
        autoescape=select_autoescape([]),
    )
    expected_script = env.get_template("commit_msg_hook.jinja2").render()
    actual_script = hook_file.read_text(encoding="utf-8")
    assert actual_script == expected_script

    # Verify file is executable (user executable bit should be set)
    mode = stat.S_IMODE(hook_file.stat().st_mode)
    assert mode & stat.S_IXUSR, "Expected commit-msg hook to be executable"

    # Verify subprocess.run was called once with git config core.hooksPath
    assert len(runs) == 1
    cmd, cwd, check_flag = runs[0]
    assert cmd == ["git", "config", "--local", "core.hooksPath", str(hooks_dir)]
    assert cwd == repo
    assert check_flag is False
