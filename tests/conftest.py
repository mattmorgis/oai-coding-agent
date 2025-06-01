import pytest

import oai_coding_agent.cli as cli_module
from oai_coding_agent.runtime_config import RuntimeConfig


@pytest.fixture
def console_main_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[RuntimeConfig]:
    """
    Monkeypatch oai_coding_agent.cli.console_main to capture calls.
    Returns a list of RuntimeConfig objects.
    """
    calls: list[RuntimeConfig] = []

    async def fake_main(config: RuntimeConfig) -> None:
        calls.append(config)

    monkeypatch.setattr(cli_module, "console_main", fake_main)
    return calls
