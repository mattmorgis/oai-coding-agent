import logging
import shutil
import subprocess
from pathlib import Path

import pytest
import typer

from oai_coding_agent.preflight import (
    run_preflight_checks,
)


def test_run_preflight_success(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Simulate git, node, and docker all present and returning versions
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")

    def fake_run(
        cmd, cwd=None, capture_output=None, text=None, check=None
    ) -> subprocess.CompletedProcess[str]:
        if cmd[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="true\n")
        if cmd[:2] == ["node", "--version"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="v14.17.0\n")
        if cmd[:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:2] == ["docker", "--version"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Docker version 20.10.7, build abcdef1\n"
            )
        pytest.fail(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    caplog.set_level(logging.INFO)
    run_preflight_checks(Path("/some/repo"))

    # Ensure versions are logged at INFO level
    assert any(
        "Detected Node.js version: v14.17.0" in record.getMessage()
        for record in caplog.records
    )
    assert any(
        "Detected Docker version: Docker version 20.10.7, build abcdef1"
        in record.getMessage()
        for record in caplog.records
    )


def test_run_preflight_git_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # Simulate git not inside worktree, node and docker ok
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")

    def fake_run(
        cmd, cwd=None, capture_output=None, text=None, check=None
    ) -> subprocess.CompletedProcess[str]:
        if cmd[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 1, stdout="false\n")
        if cmd[:2] == ["node", "--version"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="v14.17.0\n")
        if cmd[:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:2] == ["docker", "--version"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="Docker version x\n")
        pytest.fail(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(typer.Exit) as excinfo:
        run_preflight_checks(Path("/not/a/repo"))
    captured = capsys.readouterr()

    assert "Path '/not/a/repo' is not inside a Git worktree." in captured.err
    assert excinfo.value.exit_code == 1


def test_run_preflight_node_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # Simulate node missing, git and docker ok
    monkeypatch.setattr(
        shutil, "which", lambda tool: None if tool == "node" else f"/usr/bin/{tool}"
    )

    def fake_run(
        cmd, cwd=None, capture_output=None, text=None, check=None
    ) -> subprocess.CompletedProcess[str]:
        if cmd[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="true\n")
        if cmd[:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:2] == ["docker", "--version"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="Docker version x\n")
        pytest.fail(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(typer.Exit) as excinfo:
        run_preflight_checks(Path("/repo"))
    captured = capsys.readouterr()

    assert "Node.js binary not found on PATH" in captured.err
    assert excinfo.value.exit_code == 1


def test_run_preflight_docker_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # Simulate docker missing, git and node ok
    monkeypatch.setattr(
        shutil, "which", lambda tool: None if tool == "docker" else f"/usr/bin/{tool}"
    )

    def fake_run(
        cmd, cwd=None, capture_output=None, text=None, check=None
    ) -> subprocess.CompletedProcess[str]:
        if cmd[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="true\n")
        if cmd[:2] == ["node", "--version"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="v14.17.0\n")
        pytest.fail(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(typer.Exit) as excinfo:
        run_preflight_checks(Path())
    captured = capsys.readouterr()

    assert "Docker binary not found on PATH" in captured.err
    assert excinfo.value.exit_code == 1
