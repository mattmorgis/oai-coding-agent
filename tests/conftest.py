from typing import Any, AsyncIterator
from unittest.mock import Mock

from oai_coding_agent.agent import AgentProtocol
from oai_coding_agent.runtime_config import RuntimeConfig


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.run_called = False
        self.run_args: list[str] = []

    async def __aenter__(self) -> "MockAgent":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    async def run(
        self,
        user_input: str,
    ) -> AsyncIterator[Any]:
        self.run_called = True
        self.run_args.append(user_input)

        async def empty_stream() -> AsyncIterator[Any]:
            if False:
                yield

        return empty_stream()


class MockConsole:
    """Mock console for testing."""

    def __init__(self, agent: AgentProtocol):
        self.agent = agent
        self.run_called = False

    async def run(self) -> None:
        self.run_called = True
