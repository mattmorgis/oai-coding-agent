from typing import Any, AsyncIterator, Optional
from unittest.mock import Mock

from agents import RunResultStreaming

from oai_coding_agent.agent import AgentProtocol
from oai_coding_agent.agent.events import (
    MessageOutputEvent,
    ReasoningEvent,
    ToolCallEvent,
)
from oai_coding_agent.runtime_config import RuntimeConfig


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.run_called = False
        self.run_args: list[str] = []
        self._previous_response_id: Optional[str] = None

    async def __aenter__(self) -> "MockAgent":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    async def run(
        self,
        user_input: str,
    ) -> tuple[
        AsyncIterator[ToolCallEvent | ReasoningEvent | MessageOutputEvent],
        RunResultStreaming,
    ]:
        self.run_called = True
        self.run_args.append(user_input)

        async def empty_stream() -> AsyncIterator[
            ToolCallEvent | ReasoningEvent | MessageOutputEvent
        ]:
            if False:
                # This is never executed, just for type checking
                yield ToolCallEvent(name="dummy", arguments="{}")

        # Create a mock of RunResultStreaming
        mock_result = Mock(spec=RunResultStreaming)
        # Set the last_response_id attribute
        mock_result.last_response_id = "mock_response_id"

        return empty_stream(), mock_result


class MockConsole:
    """Mock console for testing."""

    def __init__(self, agent: AgentProtocol):
        self.agent = agent
        self.run_called = False

    async def run(self) -> None:
        self.run_called = True
