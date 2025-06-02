from pathlib import Path

import pytest
from conftest import MockAgent, MockConsole
from typer.testing import CliRunner

import oai_coding_agent.cli as cli_module
from oai_coding_agent.agent import AgentProtocol
from oai_coding_agent.cli import create_app
from oai_coding_agent.console.console import Console
from oai_coding_agent.runtime_config import ModeChoice, ModelChoice, RuntimeConfig


@pytest.fixture
def mock_agents() -> list[MockAgent]:
    """Track created mock agents."""
    return []


@pytest.fixture
def mock_consoles() -> list[MockConsole]:
    """Track created mock consoles."""
    return []


@pytest.fixture(autouse=True)
def stub_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub preflight checks for CLI tests to not block execution
    monkeypatch.setattr(
        cli_module, "run_preflight_checks", lambda repo_path: (None, None)
    )


def test_cli_invokes_console_with_explicit_flags(
    mock_agents: list[MockAgent],
    mock_consoles: list[MockConsole],
    tmp_path: Path,
) -> None:
    def test_agent_factory(config: RuntimeConfig) -> AgentProtocol:
        agent = MockAgent(config)
        mock_agents.append(agent)
        return agent

    def test_console_factory(agent: AgentProtocol) -> Console:
        console = MockConsole(agent)
        mock_consoles.append(console)
        return console

    app = create_app(test_agent_factory, test_console_factory)
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
    assert len(mock_agents) == 1
    assert len(mock_consoles) == 1

    agent = mock_agents[0]
    assert agent.config.repo_path == tmp_path
    assert agent.config.model == ModelChoice.o3
    assert agent.config.openai_api_key == "TESTKEY"
    assert agent.config.mode == ModeChoice.default

    console = mock_consoles[0]
    assert console.run_called


def test_cli_uses_environment_defaults(
    monkeypatch: pytest.MonkeyPatch,
    mock_agents: list[MockAgent],
    mock_consoles: list[MockConsole],
    tmp_path: Path,
) -> None:
    # Set environment variables for API keys
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ENVGH")

    def test_agent_factory(config: RuntimeConfig) -> AgentProtocol:
        agent = MockAgent(config)
        mock_agents.append(agent)
        return agent

    def test_console_factory(agent: AgentProtocol) -> Console:
        console = MockConsole(agent)
        mock_consoles.append(console)
        return console

    app = create_app(test_agent_factory, test_console_factory)
    runner = CliRunner()
    result = runner.invoke(app, ["--repo-path", str(tmp_path)])
    assert result.exit_code == 0
    assert len(mock_agents) == 1

    agent = mock_agents[0]
    assert agent.config.repo_path == tmp_path
    assert agent.config.model == ModelChoice.codex_mini_latest
    assert agent.config.openai_api_key == "ENVKEY"
    assert agent.config.mode == ModeChoice.default


def test_cli_uses_cwd_as_default_repo_path(
    monkeypatch: pytest.MonkeyPatch,
    mock_agents: list[MockAgent],
    mock_consoles: list[MockConsole],
) -> None:
    # Set environment variables for API keys
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ENVGH")

    # Get the actual current working directory
    expected_cwd = Path.cwd()

    def test_agent_factory(config: RuntimeConfig) -> AgentProtocol:
        agent = MockAgent(config)
        mock_agents.append(agent)
        return agent

    def test_console_factory(agent: AgentProtocol) -> Console:
        console = MockConsole(agent)
        mock_consoles.append(console)
        return console

    app = create_app(test_agent_factory, test_console_factory)
    runner = CliRunner()
    result = runner.invoke(app, [])  # No --repo-path specified
    assert result.exit_code == 0
    assert len(mock_agents) == 1

    agent = mock_agents[0]
    assert agent.config.repo_path == expected_cwd
    assert agent.config.model == ModelChoice.codex_mini_latest
    assert agent.config.openai_api_key == "ENVKEY"
    assert agent.config.mode == ModeChoice.default


def test_cli_prompt_invokes_headless_main(
    monkeypatch: pytest.MonkeyPatch,
    mock_agents: list[MockAgent],
    mock_consoles: list[MockConsole],
    tmp_path: Path,
) -> None:
    # Set environment variables for API keys
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ENVGH")

    def test_agent_factory(config: RuntimeConfig) -> AgentProtocol:
        agent = MockAgent(config)
        mock_agents.append(agent)
        return agent

    def test_console_factory(agent: AgentProtocol) -> Console:
        console = MockConsole(agent)
        mock_consoles.append(console)
        return console

    app = create_app(test_agent_factory, test_console_factory)
    runner = CliRunner()
    result = runner.invoke(
        app, ["--repo-path", str(tmp_path), "--prompt", "Do awesome things"]
    )
    assert result.exit_code == 0
    assert len(mock_agents) == 1

    agent = mock_agents[0]
    assert agent.config.repo_path == tmp_path
    assert agent.config.model == ModelChoice.codex_mini_latest
    assert agent.config.openai_api_key == "ENVKEY"
    assert agent.config.mode == ModeChoice.async_
    assert agent.config.prompt == "Do awesome things"


def test_cli_prompt_stdin_invokes_headless_main(
    monkeypatch: pytest.MonkeyPatch,
    mock_agents: list[MockAgent],
    mock_consoles: list[MockConsole],
    tmp_path: Path,
) -> None:
    # Set environment variables for API keys
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ENVGH")

    def test_agent_factory(config: RuntimeConfig) -> AgentProtocol:
        agent = MockAgent(config)
        mock_agents.append(agent)
        return agent

    def test_console_factory(agent: AgentProtocol) -> Console:
        console = MockConsole(agent)
        mock_consoles.append(console)
        return console

    app = create_app(test_agent_factory, test_console_factory)
    runner = CliRunner()
    prompt_str = "Huge prompt content that exceeds usual limits"
    result = runner.invoke(
        app, ["--repo-path", str(tmp_path), "--prompt", "-"], input=prompt_str
    )
    assert result.exit_code == 0
    assert len(mock_agents) == 1

    agent = mock_agents[0]
    assert agent.config.repo_path == tmp_path
    assert agent.config.model == ModelChoice.codex_mini_latest
    assert agent.config.openai_api_key == "ENVKEY"
    assert agent.config.mode == ModeChoice.async_
    assert agent.config.prompt == prompt_str
