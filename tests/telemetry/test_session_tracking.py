from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import MockAgent, MockConsole
from typer.testing import CliRunner

import oai_coding_agent.cli as cli_module
from oai_coding_agent.agent import AgentProtocol
from oai_coding_agent.cli import create_app
from oai_coding_agent.console.console import ConsoleInterface
from oai_coding_agent.runtime_config import RuntimeConfig
from oai_coding_agent.xdg import get_data_dir


@pytest.fixture
def mock_agent_factory() -> Any:
    created_agent: MockAgent | None = None

    def factory(config: RuntimeConfig) -> AgentProtocol:
        nonlocal created_agent
        created_agent = MockAgent(config)
        return created_agent

    class FactoryResult:
        @property
        def agent(self) -> MockAgent | None:
            return created_agent

        @property
        def factory(self) -> Any:
            return factory

    return FactoryResult()


@pytest.fixture
def mock_console_factory() -> Any:
    created_console: MockConsole | None = None

    def factory(agent: AgentProtocol) -> ConsoleInterface:
        nonlocal created_console
        created_console = MockConsole(agent)
        return created_console

    class FactoryResult:
        @property
        def console(self) -> MockConsole | None:
            return created_console

        @property
        def factory(self) -> Any:
            return factory

    return FactoryResult()


@pytest.fixture(autouse=True)
def stub_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    # Avoid running real preflight checks
    monkeypatch.setattr(
        cli_module, "run_preflight_checks", lambda repo_path: (None, None)
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_session_records_written_and_user_id_persisted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_agent_factory: Any,
    mock_console_factory: Any,
) -> None:
    # Isolate data dir and set required env
    xdg_data = tmp_path / "xdg"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))
    monkeypatch.setenv("OPENAI_API_KEY", "ENVKEY")
    monkeypatch.setenv("GITHUB_TOKEN", "ENVGH")

    app = create_app(mock_agent_factory.factory, mock_console_factory.factory)
    runner = CliRunner()

    # First run
    result1 = runner.invoke(app, ["--repo-path", str(tmp_path)])
    assert result1.exit_code == 0

    data_dir = get_data_dir()
    sessions_path = data_dir / "sessions.jsonl"
    user_id_path = data_dir / "user_id"

    assert sessions_path.exists()
    assert user_id_path.exists()

    rows1 = _read_jsonl(sessions_path)
    # Expect a start and an end record
    assert len(rows1) == 2
    assert rows1[0]["type"] == "session_start"
    assert rows1[1]["type"] == "session_end"
    assert rows1[0]["session_id"] == rows1[1]["session_id"]

    persisted_user_id = user_id_path.read_text(encoding="utf-8").strip()
    assert rows1[0]["user_id"] == persisted_user_id
    assert rows1[1]["user_id"] == persisted_user_id

    # Second run – should reuse the same user_id and append two more rows
    # Create a fresh Typer app to simulate a new process
    app2 = create_app(mock_agent_factory.factory, mock_console_factory.factory)
    result2 = runner.invoke(app2, ["--repo-path", str(tmp_path)])
    assert result2.exit_code == 0

    rows2 = _read_jsonl(sessions_path)
    assert len(rows2) == 4
    assert rows2[2]["type"] == "session_start"
    assert rows2[3]["type"] == "session_end"
    assert rows2[2]["user_id"] == persisted_user_id
    assert rows2[3]["user_id"] == persisted_user_id
