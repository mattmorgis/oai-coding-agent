from pathlib import Path
from typing import Any

import pytest
from conftest import MockAgent
from rich.console import Console

import oai_coding_agent.console.rendering as rendering
import oai_coding_agent.console.repl_console as repl_console_module
from oai_coding_agent.console.console import ReplConsole
from oai_coding_agent.runtime_config import (
    ModeChoice,
    ModelChoice,
    RuntimeConfig,
)
from oai_coding_agent.xdg import get_data_dir


class DummyPromptSession:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def prompt_async(self) -> str:
        # Immediately exit on slash command
        return "/exit"


@pytest.fixture(autouse=True)
def setup_repl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Console:
    # Redirect console output to recorder and disable clear
    recorder = Console(record=True, width=80)
    monkeypatch.setattr(rendering, "console", recorder)
    monkeypatch.setattr(repl_console_module, "console", recorder)

    # Force history path into tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Monkeypatch prompt session only
    monkeypatch.setattr(repl_console_module, "PromptSession", DummyPromptSession)

    return recorder


@pytest.mark.asyncio
async def test_repl_console_exits_on_exit_and_prints_header(
    setup_repl: Console, tmp_path: Path
) -> None:
    recorder = setup_repl
    config = RuntimeConfig(
        openai_api_key="APIKEY",
        github_token="GHTOKEN",
        model=ModelChoice.codex_mini_latest,
        repo_path=tmp_path,
        mode=ModeChoice.default,
    )

    # Create agent and console directly
    agent = MockAgent(config)
    console = ReplConsole(agent)
    await console.run()

    output = recorder.export_text()
    # Header includes agent name and model
    assert "OAI CODING AGENT" in output
    assert "codex-mini-latest" in output

    # Ensure history directory was created under tmp_path
    history_dir = get_data_dir()
    assert history_dir.is_dir(), "History directory should be created"
