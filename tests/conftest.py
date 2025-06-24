import asyncio
from typing import Any

from oai_coding_agent.agent import AgentEvent, AgentProtocol, AsyncAgentProtocol
from oai_coding_agent.runtime_config import RuntimeConfig


class MockAgent(AsyncAgentProtocol):
    """Mock agent for testing."""

    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.max_turns = 100
        self.events = asyncio.Queue[AgentEvent]()
        self.start_init_event: asyncio.Event | None = None
        self.run_called = False
        self.run_args: list[str] = []

    async def __aenter__(self) -> "MockAgent":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    async def run(
        self,
        user_input: str,
    ) -> None:
        self.run_called = True
        self.run_args.append(user_input)

    async def cancel(self) -> None:
        pass

    @property
    def is_processing(self) -> bool:
        return False


class MockConsole:
    """Mock console for testing."""

    def __init__(self, agent: AgentProtocol):
        self.agent = agent
        self.run_called = False

    async def run(self) -> None:
        self.run_called = True
