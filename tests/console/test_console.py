from pathlib import Path
from typing import Any, AsyncGenerator, Optional, Self
from unittest.mock import Mock

import pytest
from rich.console import Console

import oai_coding_agent.console.console as console_module
import oai_coding_agent.console.rendering as rendering
from oai_coding_agent.runtime_config import ModeChoice, ModelChoice, RuntimeConfig


class DummyPromptSession:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def prompt(self, prompt_str: str) -> str:
        # Immediately exit on slash command
        return "/exit"


class DummyAgent:
    def __init__(self, config: RuntimeConfig):
        self.config = config

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass

    async def run(
        self, user_input: str, prev_id: Optional[str] = None
    ) -> tuple[AsyncGenerator[Any, None], Any]:
        async def empty_stream() -> AsyncGenerator[Any, None]:
            if False:
                yield

        result = Mock()
        result.last_response_id = None

        return empty_stream(), result


@pytest.fixture(autouse=True)
def setup_repl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Console:
    # Redirect console output to recorder and disable clear
    recorder = Console(record=True, width=80)
    monkeypatch.setattr(rendering, "console", recorder)
    monkeypatch.setattr(console_module, "console", recorder)
    monkeypatch.setattr(rendering, "clear_terminal", lambda: None)
    monkeypatch.setattr(console_module, "clear_terminal", lambda: None)

    # Force history path into tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Monkeypatch prompt session only
    monkeypatch.setattr(console_module, "PromptSession", DummyPromptSession)

    return recorder


@pytest.mark.asyncio
async def test_repl_console_exits_on_exit_and_prints_header(
    setup_repl: Console, tmp_path: Path
) -> None:
    recorder = setup_repl
    config = RuntimeConfig(
        openai_api_key="APIKEY",
        github_personal_access_token="GHTOKEN",
        model=ModelChoice.codex_mini_latest,
        repo_path=tmp_path,
        mode=ModeChoice.default,
    )

    # Create agent and console directly
    agent = DummyAgent(config)
    console = console_module.ReplConsole(agent)
    await console.run()

    output = recorder.export_text()
    # Header includes agent name and model
    assert "OAI CODING AGENT" in output
    assert "codex-mini-latest" in output

    # Ensure history directory was created under tmp_path
    history_dir = tmp_path / ".oai_coding_agent"
    assert history_dir.is_dir(), "History directory should be created"
