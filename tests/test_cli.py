import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

import oai_coding_agent.cli as cli_module
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


def test_cli_prompt_invokes_batch_main(monkeypatch, rich_tui_calls, tmp_path):
    # Monkeypatch batch_main to capture calls for non-interactive mode
    calls = []
    async def fake_batch_main(repo_path, model, api_key, mode, prompt):
        calls.append((repo_path, model, api_key, mode, prompt))
    monkeypatch.setattr(cli_module, "batch_main", fake_batch_main)
    # Simulate running from cwd and reading key from environment
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")

    runner = CliRunner()
    result = runner.invoke(app, ["--prompt", "Do awesome things"])
    assert result.exit_code == 0
    assert calls == [(tmp_path, "codex-mini-latest", "ENVKEY", "async", "Do awesome things")]
    assert rich_tui_calls == []


def test_cli_prompt_file_invokes_batch_main(monkeypatch, rich_tui_calls, tmp_path):
    # Create a markdown file for the prompt
    prompt_file = tmp_path / "task.md"
    prompt_file.write_text("Please summarize this project.")
    # Monkeypatch batch_main to capture calls
    calls = []
    async def fake_batch_main(repo_path, model, api_key, mode, prompt):
        calls.append((repo_path, model, api_key, mode, prompt))
    monkeypatch.setattr(cli_module, "batch_main", fake_batch_main)
    # Simulate running from cwd and reading key from environment
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")

    runner = CliRunner()
    result = runner.invoke(app, ["--prompt", str(prompt_file)])
    assert result.exit_code == 0
    assert calls == [
        (
            tmp_path,
            "codex-mini-latest",
            "ENVKEY",
            "async",
            "Please summarize this project.",
        )
    ]
    assert rich_tui_calls == []
