import pytest
from typer.testing import CliRunner

import oai_coding_agent.cli as cli_module
from oai_coding_agent.cli import app


@pytest.fixture(autouse=True)
def set_github_env(monkeypatch):
    # Ensure GitHub token is set for CLI tests by default
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ENV_GH_TOKEN")
    yield


@pytest.fixture(autouse=True)
def stub_preflight(monkeypatch):
    # Stub preflight checks for CLI tests to not block execution
    monkeypatch.setattr(cli_module, "run_preflight_checks", lambda repo_path: None)


def test_cli_invokes_rich_tui_with_flags(console_main_calls, tmp_path):
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


def test_cli_uses_defaults(monkeypatch, console_main_calls, tmp_path):
    # Simulate running from cwd and reading keys from environment
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ENVGH")

    runner = CliRunner()
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert console_main_calls == [(tmp_path, "codex-mini-latest", "ENVKEY", "default")]


def test_cli_prompt_invokes_headless_main(monkeypatch, console_main_calls, tmp_path):
    # Monkeypatch headless_main to capture calls for headless (async) mode
    calls = []

    async def fake_batch_main(repo_path, model, api_key, gh_token, mode, prompt):
        calls.append((repo_path, model, api_key, mode, prompt))

    monkeypatch.setattr(cli_module, "headless_main", fake_batch_main)
    # Simulate running from cwd and reading keys from environment
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ENVGH")

    runner = CliRunner()
    result = runner.invoke(app, ["--prompt", "Do awesome things"])
    assert result.exit_code == 0
    assert calls == [
        (tmp_path, "codex-mini-latest", "ENVKEY", "async", "Do awesome things")
    ]
    assert console_main_calls == []


def test_cli_prompt_stdin_invokes_headless_main(
    monkeypatch, console_main_calls, tmp_path
):
    # Monkeypatch headless_main to capture calls for headless (async) mode
    calls = []

    async def fake_batch_main(repo_path, model, api_key, gh_token, mode, prompt):
        calls.append((repo_path, model, api_key, mode, prompt))

    monkeypatch.setattr(cli_module, "headless_main", fake_batch_main)
    # Simulate running from cwd and reading keys from environment
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ENVGH")

    runner = CliRunner()
    prompt_str = "Huge prompt content that exceeds usual limits"
    result = runner.invoke(app, ["--prompt", "-"], input=prompt_str)
    assert result.exit_code == 0
    assert calls == [(tmp_path, "codex-mini-latest", "ENVKEY", "async", prompt_str)]
    assert console_main_calls == []
