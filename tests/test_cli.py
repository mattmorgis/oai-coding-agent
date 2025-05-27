import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from oai_coding_agent.cli import app


def test_cli_invokes_rich_tui_with_flags(rich_tui_calls, tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--openai-api-key",
            "TESTKEY",
            "--model",
            "o3",
            "--repo-path",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert rich_tui_calls == [(tmp_path, "o3", "TESTKEY", "default")]


def test_cli_uses_defaults(monkeypatch, rich_tui_calls, tmp_path):
    # Simulate running from cwd and reading key from environment
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")

    runner = CliRunner()
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert rich_tui_calls == [(tmp_path, "codex-mini-latest", "ENVKEY", "default")]
