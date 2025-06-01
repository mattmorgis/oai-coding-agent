from pathlib import Path

import pytest
from typer.testing import CliRunner

import oai_coding_agent.cli as cli_module
from oai_coding_agent.cli import app


@pytest.fixture(autouse=True)
def stub_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub preflight checks for CLI tests to not block execution
    monkeypatch.setattr(cli_module, "run_preflight_checks", lambda repo_path: None)


def test_cli_invokes_console_with_explicit_flags(
    console_main_calls: list[tuple[Path, str, str, str]], tmp_path: Path
) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--openai-api-key",
            "TESTKEY",
            "--github-personal-access-token",
            "GHKEY",
            "--model",
            "o3",
            "--repo-path",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert console_main_calls == [(tmp_path, "o3", "TESTKEY", "default")]


def test_cli_uses_environment_defaults(
    monkeypatch: pytest.MonkeyPatch,
    console_main_calls: list[tuple[Path, str, str, str]],
    tmp_path: Path,
) -> None:
    # Set environment variables for API keys
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ENVGH")

    runner = CliRunner()
    result = runner.invoke(app, ["--repo-path", str(tmp_path)])
    assert result.exit_code == 0
    assert console_main_calls == [(tmp_path, "codex-mini-latest", "ENVKEY", "default")]


def test_cli_uses_cwd_as_default_repo_path(
    monkeypatch: pytest.MonkeyPatch,
    console_main_calls: list[tuple[Path, str, str, str]],
) -> None:
    # Set environment variables for API keys
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ENVGH")

    # Get the actual current working directory
    expected_cwd = Path.cwd()

    runner = CliRunner()
    result = runner.invoke(app, [])  # No --repo-path specified
    assert result.exit_code == 0
    assert console_main_calls == [
        (expected_cwd, "codex-mini-latest", "ENVKEY", "default")
    ]


def test_cli_prompt_invokes_headless_main(
    monkeypatch: pytest.MonkeyPatch,
    console_main_calls: list[tuple[Path, str, str, str]],
    headless_main_calls: list[tuple[Path, str, str, str, str]],
    tmp_path: Path,
) -> None:
    # Set environment variables for API keys
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ENVGH")

    runner = CliRunner()
    result = runner.invoke(
        app, ["--repo-path", str(tmp_path), "--prompt", "Do awesome things"]
    )
    assert result.exit_code == 0
    assert headless_main_calls == [
        (tmp_path, "codex-mini-latest", "ENVKEY", "async", "Do awesome things")
    ]
    assert console_main_calls == []


def test_cli_prompt_stdin_invokes_headless_main(
    monkeypatch: pytest.MonkeyPatch,
    console_main_calls: list[tuple[Path, str, str, str]],
    headless_main_calls: list[tuple[Path, str, str, str, str]],
    tmp_path: Path,
) -> None:
    # Set environment variables for API keys
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ENVGH")

    runner = CliRunner()
    prompt_str = "Huge prompt content that exceeds usual limits"
    result = runner.invoke(
        app, ["--repo-path", str(tmp_path), "--prompt", "-"], input=prompt_str
    )
    assert result.exit_code == 0
    assert headless_main_calls == [
        (tmp_path, "codex-mini-latest", "ENVKEY", "async", prompt_str)
    ]
    assert console_main_calls == []
