from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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


async def test_setup_openai_secret_use_current(
    runtime_config_with_github: RuntimeConfig,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Use existing OpenAI key for setup_openai_secret happy path."""
    console = GitHubWorkflowConsole(runtime_config_with_github)
    with patch.object(console.prompt_session, "prompt_async", return_value="1"):
        with patch.object(
            console, "_create_repository_secret", return_value=True
        ) as mock_secret:
            result = await console.setup_openai_secret()
            assert result is True
            mock_secret.assert_called_once_with(
                runtime_config_with_github.openai_api_key
            )
    captured = capsys.readouterr()
    assert "Setup OpenAI API Key" in captured.out


async def test_prompt_for_new_api_key_valid(
    github_workflow_console: GitHubWorkflowConsole,
) -> None:
    """Entering a valid sk- key returns it."""
    with patch.object(
        github_workflow_console.prompt_session,
        "prompt_async",
        return_value="sk-testkey123",
    ):
        api_key = await github_workflow_console._prompt_for_new_api_key()
        assert api_key == "sk-testkey123"


def test_create_repository_secret_success(
    runtime_config_with_github: RuntimeConfig,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Creating repository secret happy path."""
    console = GitHubWorkflowConsole(runtime_config_with_github)
    fake_repo = MagicMock()

    class FakeGH:
        def __init__(self, token: str) -> None:
            assert token == runtime_config_with_github.github_token

        def get_repo(self, repo_name: str) -> MagicMock:
            assert repo_name == runtime_config_with_github.github_repo
            return fake_repo

    monkeypatch.setattr(
        "oai_coding_agent.console.github_workflow_console.Github", FakeGH
    )
    fake_repo.create_secret.return_value = None
    result = console._create_repository_secret("new-key")
    assert result is True
    captured = capsys.readouterr()
    assert "Created repository secret 'OPENAI_API_KEY'" in captured.out


def test_create_workflow_pr_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path for create_workflow_pr."""
    console = GitHubWorkflowConsole(
        RuntimeConfig(
            openai_api_key="k",
            github_token="t",
            github_repo="r",
            model=ModelChoice.codex_mini_latest,
            repo_path=Path(),
            mode=ModeChoice.default,
        )
    )
    monkeypatch.setattr(console, "_check_prerequisites", lambda: True)
    monkeypatch.setattr(console, "load_workflow_template", lambda: "dummy")
    monkeypatch.setattr(console, "_initialize_github_repo", lambda: MagicMock())
    monkeypatch.setattr(console, "_create_or_update_branch", lambda repo: "branch")
    monkeypatch.setattr(
        console, "_create_or_update_workflow_file", lambda repo, c, b: True
    )
    monkeypatch.setattr(console, "_create_pull_request", lambda repo, b: True)
    result = console.create_workflow_pr()
    assert result is True


async def test_run_happy_path(
    runtime_config_with_github: RuntimeConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path for run(): all substeps return True."""
    console = GitHubWorkflowConsole(runtime_config_with_github)

    async def stub_true_async(*args: object, **kwargs: object) -> bool:
        return True

    monkeypatch.setattr(console, "install_app", stub_true_async)
    monkeypatch.setattr(console, "setup_openai_secret", stub_true_async)
    monkeypatch.setattr(console, "create_workflow_pr", lambda: True)
    result = await console.run()
    assert result is True
