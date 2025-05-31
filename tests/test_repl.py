import pytest
from pathlib import Path
from rich.console import Console
from typing import Any, AsyncGenerator, Self

import oai_coding_agent.console.repl as repl_module
import oai_coding_agent.console.rendering as rendering


class DummyPromptSession:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def prompt(self, prompt_str: str) -> str:
        # Immediately exit on slash command
        return "/exit"


class DummyAgentSession:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass

    async def run_step(
        self, user_input: str, prev_id: Any
    ) -> tuple[AsyncGenerator[Any, None], Any]:
        async def empty_stream() -> AsyncGenerator[Any, None]:
            if False:
                yield

        class Result:
            last_response_id = None

        return empty_stream(), Result()


@pytest.fixture(autouse=True)
def setup_repl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Console:
    # Redirect console output to recorder and disable clear
    recorder = Console(record=True, width=80)
    monkeypatch.setattr(rendering, "console", recorder)
    monkeypatch.setattr(repl_module, "console", recorder)
    monkeypatch.setattr(rendering, "clear_terminal", lambda: None)
    monkeypatch.setattr(repl_module, "clear_terminal", lambda: None)

    # Force history path into tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Monkeypatch prompt session and agent session
    monkeypatch.setattr(repl_module, "PromptSession", DummyPromptSession)
    monkeypatch.setattr(repl_module, "AgentSession", DummyAgentSession)

    return recorder


@pytest.mark.asyncio
async def test_repl_main_exits_on_exit_and_prints_header(
    setup_repl: Console, tmp_path: Path
) -> None:
    recorder = setup_repl
    await repl_module.main(tmp_path, "model-x", "APIKEY", "GHTOKEN")

    output = recorder.export_text()
    # Header includes agent name and model
    assert "OAI CODING AGENT" in output
    assert "model-x" in output

    # Ensure history directory was created under tmp_path
    history_dir = tmp_path / ".oai_coding_agent"
    assert history_dir.is_dir(), "History directory should be created"
