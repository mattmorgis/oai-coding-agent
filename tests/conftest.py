from typing import Optional, Union

import pytest

import oai_coding_agent.cli as cli_module
from oai_coding_agent.runtime_config import RuntimeConfig


@pytest.fixture
def console_main_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[Union[RuntimeConfig, tuple[RuntimeConfig, Optional[str]]]]:
    """
    Monkeypatch oai_coding_agent.cli.console_main to capture calls.
    Returns a list of either RuntimeConfig (REPL mode) or (RuntimeConfig, prompt) tuples (headless mode).
    """
    calls: list[Union[RuntimeConfig, tuple[RuntimeConfig, Optional[str]]]] = []

    async def fake_main(config: RuntimeConfig, prompt: Optional[str] = None) -> None:
        if prompt is None:
            calls.append(config)
        else:
            calls.append((config, prompt))

    monkeypatch.setattr(cli_module, "console_main", fake_main)
    return calls
