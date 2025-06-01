import pytest

import oai_coding_agent.cli as cli_module
from oai_coding_agent.runtime_config import RuntimeConfig


@pytest.fixture
def console_main_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[RuntimeConfig]:
    """
    Monkeypatch oai_coding_agent.cli.console_main to capture calls instead of running the console REPL.
    Returns a list of RuntimeConfig objects.
    """
    calls = []

    async def fake_main(config: RuntimeConfig) -> None:
        calls.append(config)

    monkeypatch.setattr(cli_module, "console_main", fake_main)
    return calls


@pytest.fixture
def headless_main_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[RuntimeConfig, str]]:
    """
    Monkeypatch oai_coding_agent.cli.headless_main to capture calls instead of running headless mode.
    Returns a list of (RuntimeConfig, prompt) tuples.
    """
    calls = []

    async def fake_headless_main(config: RuntimeConfig, prompt: str) -> None:
        calls.append((config, prompt))

    monkeypatch.setattr(cli_module, "headless_main", fake_headless_main)
    return calls
