from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from github import GithubException

from oai_coding_agent.console.github_workflow_console import GitHubWorkflowConsole
from oai_coding_agent.runtime_config import ModeChoice, ModelChoice, RuntimeConfig


@pytest.fixture
def runtime_config(tmp_path: Path) -> RuntimeConfig:
    return RuntimeConfig(
        openai_api_key="test-key",
        github_token=None,
        model=ModelChoice.codex_mini_latest,
        repo_path=tmp_path,
        mode=ModeChoice.default,
    )


@pytest.fixture
def runtime_config_with_github(tmp_path: Path) -> RuntimeConfig:
    return RuntimeConfig(
        openai_api_key="test-key",
        github_token="token123",
        github_repo="owner/repo",
        model=ModelChoice.codex_mini_latest,
        repo_path=tmp_path,
        mode=ModeChoice.default,
    )


@pytest.fixture
def github_workflow_console(runtime_config: RuntimeConfig) -> GitHubWorkflowConsole:
    return GitHubWorkflowConsole(runtime_config)


async def test_install_app_success(
    github_workflow_console: GitHubWorkflowConsole, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test successful GitHub App installation flow."""
    with patch.object(
        github_workflow_console.prompt_session,
        "prompt_async",
        side_effect=["", ""],  # First for browser prompt, second for completion
    ):
        with patch("oai_coding_agent.console.github_workflow_console.webbrowser.open"):
            result = await github_workflow_console.install_app()
            assert result is True
            captured = capsys.readouterr()
            assert "Install GitHub App" in captured.out
            assert "Browser opened" in captured.out


async def test_install_app_browser_failure(
    github_workflow_console: GitHubWorkflowConsole, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test GitHub App installation when browser fails to open."""
    with patch.object(
        github_workflow_console.prompt_session,
        "prompt_async",
        side_effect=["", ""],
    ):
        with patch(
            "oai_coding_agent.console.github_workflow_console.webbrowser.open",
            side_effect=Exception("Browser error"),
        ):
            result = await github_workflow_console.install_app()
            assert result is True
            captured = capsys.readouterr()
            assert (
                "Please visit: https://github.com/apps/oai-coding-agent/installations/new"
                in captured.out
            )


async def test_install_app_basic_flow(
    github_workflow_console: GitHubWorkflowConsole, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test basic GitHub App installation flow."""
    with patch.object(
        github_workflow_console.prompt_session,
        "prompt_async",
        side_effect=["", ""],  # User presses enter twice
    ):
        with patch("oai_coding_agent.console.github_workflow_console.webbrowser.open"):
            result = await github_workflow_console.install_app()
            assert result is True
