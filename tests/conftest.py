import pytest
import oai_coding_agent.cli as cli_module


@pytest.fixture
def rich_tui_calls(monkeypatch):
    """
    Monkeypatch oai_coding_agent.cli.console_main to capture calls instead of running the console REPL.
    Returns a list of (repo_path, model, api_key, mode) tuples.
    """
    calls = []

    async def fake_main(repo_path, model, api_key, mode):
        calls.append((repo_path, model, api_key, mode))

    monkeypatch.setattr(cli_module, "console_main", fake_main)
    return calls
