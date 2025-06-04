import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import MagicMock, patch

import git
import pytest
from docker.errors import DockerException

from oai_coding_agent.preflight.preflight import (
    PreflightCheckError,
    run_preflight_checks,
)


def test_run_preflight_success(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Simulate git, node, and docker all present and returning versions
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")

    # Mock GitPython
    mock_repo = MagicMock()
    mock_origin = MagicMock()
    mock_origin.url = "https://github.com/owner/repo.git"
    mock_remotes = MagicMock()
    mock_remotes.__contains__ = lambda self, key: key == "origin"
    mock_remotes.origin = mock_origin
    mock_repo.remotes = mock_remotes
    mock_branch = MagicMock()
    mock_branch.name = "main"
    mock_repo.active_branch = mock_branch
    mock_repo.head.is_detached = False
    mock_config_writer = MagicMock()
    mock_config_writer.set_value = MagicMock(return_value=mock_config_writer)
    mock_config_writer.release = MagicMock()
    mock_repo.config_writer = MagicMock(return_value=mock_config_writer)

    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)

    def fake_run(
        cmd: Sequence[str],
        cwd: Path | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        check: bool | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["node", "--version"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="v14.17.0\n")
        pytest.fail(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Mock Docker client
    mock_docker_client = MagicMock()
    mock_docker_client.ping.return_value = True
    mock_docker_client.version.return_value = {"Version": "20.10.7"}
    mock_docker_client.close = MagicMock()

    with patch("docker.from_env", return_value=mock_docker_client):
        caplog.set_level(logging.INFO)
        github_repo, branch_name = run_preflight_checks(Path("/some/repo"))

    assert github_repo == "owner/repo"
    assert branch_name == "main"

    # Ensure versions are logged at INFO level
    assert any(
        "Detected Node.js version: v14.17.0" in record.getMessage()
        for record in caplog.records
    )
    assert any(
        "Detected Docker version: Docker version 20.10.7" in record.getMessage()
        for record in caplog.records
    )


def test_run_preflight_git_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate git not inside worktree, node and docker ok
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")

    # Mock GitPython to raise InvalidGitRepositoryError
    def raise_invalid(*args: Any, **kwargs: Any) -> None:
        raise git.InvalidGitRepositoryError()

    monkeypatch.setattr(git, "Repo", raise_invalid)

    def fake_run(
        cmd: Sequence[str],
        cwd: Path | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        check: bool | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["node", "--version"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="v14.17.0\n")
        pytest.fail(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Mock Docker client
    mock_docker_client = MagicMock()
    mock_docker_client.ping.return_value = True
    mock_docker_client.version.return_value = {"Version": "20.10.7"}
    mock_docker_client.close = MagicMock()

    with patch("docker.from_env", return_value=mock_docker_client):
        with pytest.raises(PreflightCheckError) as excinfo:
            run_preflight_checks(Path("/not/a/repo"))

    assert "Path '/not/a/repo' is not inside a Git worktree." in str(excinfo.value)
    assert len(excinfo.value.errors) == 1


def test_run_preflight_node_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate node missing, git and docker ok
    monkeypatch.setattr(
        shutil, "which", lambda tool: None if tool == "node" else f"/usr/bin/{tool}"
    )

    # Mock GitPython
    mock_repo = MagicMock()
    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)

    def fake_run(
        cmd: Sequence[str],
        cwd: Path | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        check: bool | None = None,
    ) -> subprocess.CompletedProcess[str]:
        pytest.fail(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Mock Docker client
    mock_docker_client = MagicMock()
    mock_docker_client.ping.return_value = True
    mock_docker_client.version.return_value = {"Version": "20.10.7"}
    mock_docker_client.close = MagicMock()

    with patch("docker.from_env", return_value=mock_docker_client):
        with pytest.raises(PreflightCheckError) as excinfo:
            run_preflight_checks(Path("/repo"))

    assert "Node.js binary not found on PATH" in str(excinfo.value)
    assert len(excinfo.value.errors) == 1


def test_run_preflight_docker_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate docker missing, git and node ok
    monkeypatch.setattr(
        shutil, "which", lambda tool: None if tool == "docker" else f"/usr/bin/{tool}"
    )

    # Mock GitPython
    mock_repo = MagicMock()
    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)

    def fake_run(
        cmd: Sequence[str],
        cwd: Path | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        check: bool | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["node", "--version"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="v14.17.0\n")
        pytest.fail(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(PreflightCheckError) as excinfo:
        run_preflight_checks(Path())

    assert "Docker binary not found on PATH" in str(excinfo.value)
    assert len(excinfo.value.errors) == 1


def test_run_preflight_docker_daemon_not_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulate docker daemon not running, git and node ok
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")

    # Mock GitPython
    mock_repo = MagicMock()
    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)

    def fake_run(
        cmd: Sequence[str],
        cwd: Path | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        check: bool | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["node", "--version"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="v14.17.0\n")
        pytest.fail(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Mock Docker client to raise exception when daemon not running
    with patch(
        "docker.from_env",
        side_effect=DockerException("Error while fetching server API version"),
    ):
        with pytest.raises(PreflightCheckError) as excinfo:
            run_preflight_checks(Path())

    assert "Failed to connect to Docker daemon" in str(excinfo.value)
    assert len(excinfo.value.errors) == 1


def test_run_preflight_multiple_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate multiple failures: git not in worktree, node missing, docker daemon not running
    monkeypatch.setattr(
        shutil, "which", lambda tool: None if tool == "node" else f"/usr/bin/{tool}"
    )

    # Mock GitPython to raise InvalidGitRepositoryError
    def raise_invalid(*args: Any, **kwargs: Any) -> None:
        raise git.InvalidGitRepositoryError()

    monkeypatch.setattr(git, "Repo", raise_invalid)

    def fake_run(
        cmd: Sequence[str],
        cwd: Path | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        check: bool | None = None,
    ) -> subprocess.CompletedProcess[str]:
        pytest.fail(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Mock Docker client to raise exception
    with patch(
        "docker.from_env",
        side_effect=DockerException("Cannot connect to the Docker daemon"),
    ):
        with pytest.raises(PreflightCheckError) as excinfo:
            run_preflight_checks(Path("/not/a/repo"))

    # Should have 3 errors
    assert len(excinfo.value.errors) == 3
    error_messages = str(excinfo.value)
    assert "not inside a Git worktree" in error_messages
    assert "Node.js binary not found" in error_messages
    assert "Failed to connect to Docker daemon" in error_messages
