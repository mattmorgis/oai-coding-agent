"""
Agent for streaming OAI agent interactions with a local codebase.
"""

__all__ = ["Agent", "AgentProtocol"]

import logging
from contextlib import AsyncExitStack
from typing import Any, AsyncIterator, Optional, Protocol, runtime_checkable

from agents import (
    Agent as SDKAgent,
)
from agents import (
    ModelSettings,
    Runner,
    RunResultStreaming,
    StreamEvent,
    gen_trace_id,
    trace,
)
from openai.types.shared.reasoning import Reasoning

from ..runtime_config import RuntimeConfig
from .instruction_builder import build_instructions
from .mcp_servers import start_mcp_servers
from .mcp_tool_selector import get_filtered_function_tools

logger = logging.getLogger(__name__)


@runtime_checkable
class AgentProtocol(Protocol):
    """Protocol defining the interface for agents."""

    config: RuntimeConfig

    async def __aenter__(self) -> "AgentProtocol": ...

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...

    async def run(
        self,
        user_input: str,
        previous_response_id: Optional[str] = None,
    ) -> tuple[AsyncIterator[StreamEvent], RunResultStreaming]: ...


class Agent:
    """Agent that manages MCP servers, tracing, and SDK agent interactions."""

    def __init__(self, config: RuntimeConfig, max_turns: int = 100):
        self.config = config
        self.max_turns = max_turns
        self._exit_stack: Optional[AsyncExitStack] = None
        self._sdk_agent: Optional[SDKAgent] = None

    async def __aenter__(self) -> "Agent":
        # Initialize exit stack for async contexts and callbacks
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        # Start MCP servers (filesystem, CLI, Git, GitHub) and register cleanup
        mcp_servers = await start_mcp_servers(
            self.config.repo_path,
            self.config.github_personal_access_token,
            self._exit_stack,
        )

        # Begin tracing
        trace_id = gen_trace_id()
        trace_ctx = trace(workflow_name="OAI Coding Agent", trace_id=trace_id)
        trace_ctx.__enter__()
        self._exit_stack.callback(trace_ctx.__exit__, None, None, None)

        # Build instructions and fetch filtered MCP function-tools
        dynamic_instructions = build_instructions(self.config)
        function_tools = await get_filtered_function_tools(
            mcp_servers, self.config.mode.value
        )

        # Instantiate the SDK Agent with the filtered function-tools
        self._sdk_agent = SDKAgent(
            name="Coding Agent",
            instructions=dynamic_instructions,
            model=self.config.model.value,
            model_settings=ModelSettings(
                reasoning=Reasoning(summary="auto", effort="high")
            ),
            tools=function_tools,
        )

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._exit_stack:
            await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)

    async def run(
        self,
        user_input: str,
        previous_response_id: Optional[str] = None,
    ) -> tuple[AsyncIterator[StreamEvent], RunResultStreaming]:
        """
        Send one user message to the agent and return an async iterator of SDK events
        plus the underlying RunResultStreaming.
        """
        if self._sdk_agent is None:
            raise RuntimeError("Agent not initialized. Use async with context manager.")

        result = Runner.run_streamed(
            self._sdk_agent,
            user_input,
            previous_response_id=previous_response_id,
            max_turns=self.max_turns,
        )

        return result.stream_events(), result
