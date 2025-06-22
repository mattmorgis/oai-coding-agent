"""
Agent for streaming OAI agent interactions with a local codebase.
"""

__all__ = [
    "AsyncAgent",
    "HeadlessAgent",
    "AgentProtocol",
    "AsyncAgentProtocol",
    "HeadlessAgentProtocol",
]
import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, AsyncIterator, Optional, Protocol, runtime_checkable

from agents import (
    Agent as OpenAIAgent,
)
from agents import (
    ModelSettings,
    Runner,
    RunResultStreaming,
    gen_trace_id,
    trace,
)
from openai.types.responses import ResponseInputItemParam
from openai.types.shared.reasoning import Reasoning

from oai_coding_agent.agent.instruction_builder import build_instructions
from oai_coding_agent.agent.mcp_servers import start_mcp_servers
from oai_coding_agent.agent.mcp_tool_selector import get_filtered_function_tools
from oai_coding_agent.runtime_config import RuntimeConfig

from .events import (
    AgentEvent,
    map_sdk_event_to_agent_event,
)


class AgentInitializationError(BaseException):
    """Raised when the agent fails to initialize properly."""


logger = logging.getLogger(__name__)


@runtime_checkable
class AgentProtocol(Protocol):
    """Base protocol defining the common interface for all agents."""

    config: RuntimeConfig
    max_turns: int

    async def __aenter__(self) -> "AgentProtocol": ...

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...

    async def cancel(self) -> None: ...


@runtime_checkable
class AsyncAgentProtocol(AgentProtocol, Protocol):
    """Protocol for async agents with event queues and background init."""

    events: asyncio.Queue[AgentEvent]
    start_init_event: asyncio.Event | None

    async def run(
        self,
        prompt: str,
    ) -> None: ...


@runtime_checkable
class HeadlessAgentProtocol(AgentProtocol, Protocol):
    """Protocol for headless agents that return an async iterator."""

    def run(
        self,
        prompt: str,
    ) -> AsyncIterator[AgentEvent]: ...


class AsyncAgent(AsyncAgentProtocol):
    """Async agent with background initialization and message queue.

    Attributes:
        config: Runtime configuration for the agent
        max_turns: Maximum number of conversation turns allowed
        events: Queue for agent events
    """

    config: RuntimeConfig
    max_turns: int
    events: asyncio.Queue[AgentEvent]

    _agent_ready_event: asyncio.Event
    start_init_event: asyncio.Event | None
    _agent_init_task: Optional[asyncio.Task[None]]
    _agent_init_exception: Optional[AgentInitializationError]

    _prompt_queue: asyncio.Queue[str]
    _prompt_consumer_task: Optional[asyncio.Task[None]]

    _active_run_result: Optional[RunResultStreaming]
    _active_run_task: Optional[asyncio.Task[None]]

    _openai_agent: Optional[OpenAIAgent]
    _agent_cancelled_mid_run: bool
    _checkpoint_response_id: Optional[str] | None
    _pending_history: list[ResponseInputItemParam] | None

    _exit_stack: Optional[AsyncExitStack]

    def __init__(self, config: RuntimeConfig, max_turns: int = 100):
        self.config = config
        self.max_turns = max_turns
        self.events = asyncio.Queue()

        self._agent_ready_event = asyncio.Event()
        self.start_init_event = None
        self._agent_init_task = None
        self._agent_init_exception = None

        self._prompt_queue = asyncio.Queue()
        self._prompt_consumer_task = None

        self._openai_agent = None
        self._agent_cancelled_mid_run = False
        self._checkpoint_response_id = None
        self._pending_history = None

        self._active_run_result = None
        self._active_run_task = None

        self._exit_stack = None

    async def __aenter__(self) -> "AsyncAgent":
        self._agent_init_task = asyncio.create_task(self._initialize_in_background())
        self._prompt_consumer_task = asyncio.create_task(self._prompt_queue_consumer())
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._exit_stack:
            await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)

    async def _initialize_in_background(self) -> None:
        logger.info("Initializing agent in background")
        try:
            if self.start_init_event is not None:
                logger.info("Agent: awaiting start_init_event before init")
                await self.start_init_event.wait()
                logger.info("Agent: start_init_event received")
            # Initialize exit stack for async contexts
            self._exit_stack = AsyncExitStack()
            await self._exit_stack.__aenter__()
            # Start MCP servers (filesystem, CLI, Git, GitHub) and register cleanup
            mcp_servers = await start_mcp_servers(
                self.config,
                self._exit_stack,
            )

            # Build instructions and fetch filtered MCP function-tools
            dynamic_instructions = build_instructions(self.config)
            function_tools = await get_filtered_function_tools(mcp_servers, self.config)

            # Instantiate the OpenAI agent with the filtered function-tools
            self._openai_agent = OpenAIAgent(
                name="Coding Agent",
                instructions=dynamic_instructions,
                model=self.config.model.value,
                model_settings=ModelSettings(
                    reasoning=Reasoning(summary="auto", effort="high"),
                    parallel_tool_calls=True,
                ),
                tools=function_tools,
            )

        except Exception as e:
            self._agent_init_exception = AgentInitializationError(
                "Failed to initialize agent",
                e,
            )
            logger.error("Failed to initialize agent", exc_info=True)
        finally:
            self._agent_ready_event.set()

    async def _prompt_queue_consumer(self) -> None:
        await self._agent_ready_event.wait()

        if self._agent_init_exception:
            raise self._agent_init_exception

        if self._openai_agent is None:
            raise AgentInitializationError(
                "OpenAI agent not initialized, ensure used with async context"
            )

        logger.info("Agent initialized, starting prompt queue consumer")

        while True:
            prompt = await self._prompt_queue.get()
            logger.info("Prompt queue consumer got prompt: %s", prompt)
            if prompt is None:
                break

            async def _events_queue_producer(prompt: str) -> None:
                logger.info("Running agent with prompt: %s", prompt)
                input_items: str | list[ResponseInputItemParam]
                if self._pending_history:
                    logger.info(
                        "Resuming with conversation history, length: %s",
                        len(self._pending_history),
                    )
                    input_items = self._pending_history + [
                        {"role": "user", "content": prompt}
                    ]
                    prev_id = None
                    self._pending_history = None
                else:
                    logger.info(
                        "Resuming with checkpoint response id: %s",
                        self._checkpoint_response_id,
                    )
                    input_items = prompt
                    prev_id = self._checkpoint_response_id

                self._active_run_result = Runner.run_streamed(
                    self._openai_agent,  # type: ignore[arg-type]
                    input_items,
                    previous_response_id=prev_id,
                    max_turns=self.max_turns,
                )
                async for stream_event in self._active_run_result.stream_events():
                    if event := map_sdk_event_to_agent_event(stream_event):
                        await self.events.put(event)

                if not (self._agent_cancelled_mid_run):
                    self._checkpoint_response_id = (
                        self._active_run_result.last_response_id
                    )
                    logger.info(
                        "Set checkpoint response id: %s",
                        self._checkpoint_response_id,
                    )
                else:
                    logger.info("Stream ended for cancelled run")
                self._agent_cancelled_mid_run = False
                logger.info("Set _agent_cancelled_mid_run = False")

            self._active_run_task = asyncio.create_task(_events_queue_producer(prompt))
            try:
                await self._active_run_task
            except asyncio.CancelledError:
                logger.info("Prompt cancelled")
                pass
            finally:
                self._active_run_task = None
                self._prompt_queue.task_done()

    async def run(
        self,
        prompt: str,
    ) -> None:
        """
        Queue a prompt for the agent to process.
        """
        await self._prompt_queue.put(prompt)

    async def cancel(self) -> None:
        """Cancel the currently executing turn, if any."""
        logger.info("Cancelling agent")
        if self._active_run_result is not None:
            self._active_run_result.cancel()
            # When a run is cancelled, the last response ID cannot be used to resume
            # We must get the full history and pass that on the next run
            # This will include all reasoning and tool calls up until the run was cancelled
            # But omit any pending tool calls it's awaiting a response fromself._agent_cancelled_mid_run = True
            logger.info("Set _agent_cancelled_mid_run = True")
            self._pending_history = self._active_run_result.to_input_list()
            logger.info(
                "Captured history from cancelled run. Conversation length: %s",
                len(self._pending_history),
            )
            self._checkpoint_response_id = None
            logger.info("Reset checkpoint response id to None due to cancelled run")

        if self._active_run_task and not self._active_run_task.done():
            self._active_run_task.cancel()


class HeadlessAgent(HeadlessAgentProtocol):
    """Agent for headless mode without background initialization or queues.

    Attributes:
        config: Runtime configuration for the agent
        max_turns: Maximum number of conversation turns allowed
        events: Queue for agent events
    """

    config: RuntimeConfig
    max_turns: int
    events: asyncio.Queue[AgentEvent]

    _openai_agent: Optional[OpenAIAgent]
    _exit_stack: Optional[AsyncExitStack]

    def __init__(self, config: RuntimeConfig, max_turns: int = 100):
        self.config = config
        self.max_turns = max_turns
        self.events = asyncio.Queue()

        self._openai_agent = None
        self._exit_stack = None

    async def __aenter__(self) -> "HeadlessAgent":
        # Initialize exit stack for async contexts
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        # Start MCP servers (filesystem, CLI, Git, GitHub) and register cleanup
        mcp_servers = await start_mcp_servers(
            self.config,
            self._exit_stack,
        )

        # Begin tracing
        trace_id = gen_trace_id()
        trace_ctx = trace(workflow_name="OAI Coding Agent", trace_id=trace_id)
        trace_ctx.__enter__()
        self._exit_stack.callback(trace_ctx.__exit__, None, None, None)

        # Build instructions and fetch filtered MCP function-tools
        dynamic_instructions = build_instructions(self.config)
        function_tools = await get_filtered_function_tools(mcp_servers, self.config)

        # Instantiate the OpenAI agent with the filtered function-tools
        self._openai_agent = OpenAIAgent(
            name="Coding Agent",
            instructions=dynamic_instructions,
            model=self.config.model.value,
            model_settings=ModelSettings(
                reasoning=Reasoning(summary="auto", effort="high"),
                parallel_tool_calls=True,
            ),
            tools=function_tools,
        )

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._exit_stack:
            await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)

    async def run(
        self,
        prompt: str,
    ) -> AsyncIterator[AgentEvent]:
        """
        Run the agent with a single prompt and yield events as they stream.

        This is a simpler version that doesn't use queues or background tasks.
        Returns an async iterator of AgentEvent objects.
        """
        if self._openai_agent is None:
            raise AgentInitializationError(
                "OpenAI agent not initialized, ensure used with async context"
            )

        run_result = Runner.run_streamed(
            self._openai_agent,
            prompt,
            max_turns=self.max_turns,
        )

        async for stream_event in run_result.stream_events():
            if event := map_sdk_event_to_agent_event(stream_event):
                yield event

    async def cancel(self) -> None:
        """Cancel is not supported in headless agent."""
        logger.warning("Cancel is not supported in HeadlessAgent")
