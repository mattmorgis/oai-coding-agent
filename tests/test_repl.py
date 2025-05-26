import pytest
import asyncio
from pathlib import Path
from rich.console import Console

import oai_coding_agent.console.repl as repl_module
import oai_coding_agent.console.rendering as rendering


class DummyPromptSession:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def prompt(self, prompt_str):
        # Immediately exit on slash command
        return "/exit"


class DummyAgentSession:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def run_step(self, user_input, prev_id):
        async def empty_stream():
            if False:
                yield

        class Result:
            last_response_id = None

        return empty_stream(), Result()


@pytest.fixture(autouse=True)
def setup_repl(monkeypatch, tmp_path):
    # Redirect console output to recorder and disable clear
    recorder = Console(record=True, width=80)
    monkeypatch.setattr(rendering, "console", recorder)
    monkeypatch.setattr(repl_module, "console", recorder)
    monkeypatch.setattr(rendering, "clear_terminal", lambda: None)
    monkeypatch.setattr(repl_module, "clear_terminal", lambda: None)

    # Force history path into tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Monkeypatch prompt session and agent session
    created = {}

    def _prompt_factory(*args, **kwargs):
        created['kwargs'] = kwargs
        return DummyPromptSession(*args, **kwargs)

    monkeypatch.setattr(repl_module, "PromptSession", _prompt_factory)
    monkeypatch.setattr(repl_module, "AgentSession", DummyAgentSession)

    return recorder, created


@pytest.mark.asyncio
async def test_repl_main_exits_on_exit_and_prints_header(setup_repl, tmp_path):
    recorder, created = setup_repl
    await repl_module.main(tmp_path, "model-x", "APIKEY")

    output = recorder.export_text()
    # Header includes agent name and model
    assert "OAI CODING AGENT" in output
    assert "model-x" in output

    # Ensure history directory was created under tmp_path
    history_dir = tmp_path / ".oai_coding_agent"
    assert history_dir.is_dir(), "History directory should be created"
    assert created["kwargs"]["vi_mode"] is False
