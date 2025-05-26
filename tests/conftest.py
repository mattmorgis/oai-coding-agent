import pytest
import oai_coding_agent.cli as cli_module

@pytest.fixture
def rich_tui_calls(monkeypatch):
    """
    Monkeypatch oai_coding_agent.cli.rich_tui.main to capture calls instead of running the TUI.
    Returns a list of (repo_path, model, api_key) tuples.
    """
    calls = []
    async def fake_main(repo_path, model, api_key):
        calls.append((repo_path, model, api_key))
    monkeypatch.setattr(cli_module.rich_tui, "main", fake_main)
    return calls
