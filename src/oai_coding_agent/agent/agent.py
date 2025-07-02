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
import contextlib
import logging
from contextlib import AsyncExitStack
from typing import Any, AsyncIterator, Optional, Protocol, runtime_checkable

from agents import (
    Agent as OpenAIAgent,
)
from agents import (
    AgentsException,
    MaxTurnsExceeded,
    ModelSettings,
    Runner,
    RunResultStreaming,
    set_tracing_disabled,
)
from openai.types.responses import ResponseInputItemParam
from openai.types.shared.reasoning import Reasoning

from oai_coding_agent.agent.instruction_builder import build_instructions
from oai_coding_agent.agent.mcp_servers import start_mcp_servers
from oai_coding_agent.agent.mcp_tool_selector import get_filtered_function_tools
from oai_coding_agent.runtime_config import RuntimeConfig

from .events import (
    AgentEvent,
    ErrorEvent,
    map_sdk_event_to_agent_event,
)


class AgentInitializationError(BaseException):
    """Raised when the agent fails to initialize properly."""


logger = logging.getLogger(__name__)
set_tracing_disabled(disabled=True)


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

    @property
    def is_processing(self) -> bool: ...

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
    _agent_init_task: Optional[asyncio.Task[None]]
    _agent_init_exception: Optional[AgentInitializationError]

    _prompt_queue: asyncio.Queue[str]
    _prompt_consumer_task: Optional[asyncio.Task[None]]

    _active_run_result: Optional[RunResultStreaming]
    _active_run_task: Optional[asyncio.Task[None]]

    _openai_agent: Optional[OpenAIAgent]
    _conversation_history: list[ResponseInputItemParam]

    _exit_stack: Optional[AsyncExitStack]
    _shutdown_event: asyncio.Event

    def __init__(self, config: RuntimeConfig, max_turns: int = 100):
        self.config = config
        self.max_turns = max_turns
        self.events = asyncio.Queue()

        self._agent_ready_event = asyncio.Event()
        self._agent_init_task = None
        self._agent_init_exception = None

        self._prompt_queue = asyncio.Queue()
        self._prompt_consumer_task = None

        self._openai_agent = None
        self._conversation_history: list[ResponseInputItemParam] = []

        self._active_run_result = None
        self._active_run_task = None

        self._exit_stack = None
        self._shutdown_event = asyncio.Event()

    async def __aenter__(self) -> "AsyncAgent":
        self._agent_init_task = asyncio.create_task(self._initialize_in_background())
        self._prompt_consumer_task = asyncio.create_task(self._prompt_queue_consumer())

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Gracefully shut down all background tasks and MCP servers."""

        await self.cancel()

        if self._prompt_consumer_task and not self._prompt_consumer_task.done():
            await self._prompt_queue.put(None)  # type: ignore[arg-type]
            with contextlib.suppress(asyncio.CancelledError):
                await self._prompt_consumer_task

        self._shutdown_event.set()

        if self._agent_init_task and not self._agent_init_task.done():
            self._agent_init_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._agent_init_task

    async def _initialize_in_background(self) -> None:
        """Initialize MCP servers and the OpenAI agent in a background task."""
        logger.info("Initializing agent in background")

        try:
            async with AsyncExitStack() as stack:
                self._exit_stack = stack

                logger.info("Starting MCP servers")
                mcp_servers = await start_mcp_servers(
                    self.config,
                    stack,
                )

                dynamic_instructions = build_instructions(self.config)
                function_tools = await get_filtered_function_tools(
                    mcp_servers, self.config
                )

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

                logger.info("Agent background initialization complete")

                self._agent_ready_event.set()

                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    logger.info(
                        "Initialization task cancelled – cleaning up MCP servers …"
                    )
                    raise

            logger.info("Background cleanup finished")

        except Exception as e:
            if not self._agent_ready_event.is_set():
                self._agent_ready_event.set()

            self._agent_init_exception = AgentInitializationError(
                "Failed to initialize agent",
                e,
            )
            logger.error("Failed to initialize agent", exc_info=True)

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

                input_items: list[ResponseInputItemParam] = (
                    self._conversation_history + [{"role": "user", "content": prompt}]
                )

                self._active_run_result = Runner.run_streamed(
                    self._openai_agent,  # type: ignore[arg-type]
                    input_items,
                    max_turns=self.max_turns,
                )
                async for stream_event in self._active_run_result.stream_events():
                    if event := map_sdk_event_to_agent_event(stream_event):
                        await self.events.put(event)

            self._active_run_task = asyncio.create_task(_events_queue_producer(prompt))
            try:
                await self._active_run_task
            except asyncio.CancelledError:
                logger.info("Prompt cancelled")
                pass
            except MaxTurnsExceeded as e:
                logger.error("Max turns exceeded: %s", e)
                await self.events.put(ErrorEvent(message=str(e)))
            except AgentsException as e:
                logger.error("Error running agent: %s", e)
                await self.events.put(ErrorEvent(message=str(e)))
            except Exception as e:
                logger.error("Error running agent: %s", e)
                await self.events.put(ErrorEvent(message=str(e)))
            finally:
                self._conversation_history = self._active_run_result.to_input_list()  # type: ignore[union-attr]
                logger.info(
                    "Updated conversation history for next run. Conversation length: %s",
                    len(self._conversation_history),
                )
                self._active_run_task = None
                self._prompt_queue.task_done()

    @property
    def is_processing(self) -> bool:
        """Check if the agent is currently processing a prompt."""
        return self._active_run_task is not None and not self._active_run_task.done()

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
            self._conversation_history = self._active_run_result.to_input_list()
            logger.info(
                "Captured history from cancelled run. Conversation length: %s",
                len(self._conversation_history),
            )

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

    _openai_agent: Optional[OpenAIAgent]
    _run_result: Optional[RunResultStreaming]

    _exit_stack: Optional[AsyncExitStack]

    def __init__(self, config: RuntimeConfig, max_turns: int = 100):
        self.config = config
        self.max_turns = max_turns

        self._openai_agent = None
        self._run_result = None

        self._exit_stack = None

    async def __aenter__(self) -> "HeadlessAgent":
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        mcp_servers = await start_mcp_servers(
            self.config,
            self._exit_stack,
        )

        dynamic_instructions = build_instructions(self.config)
        function_tools = await get_filtered_function_tools(mcp_servers, self.config)

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

        self._run_result = Runner.run_streamed(
            self._openai_agent,
            prompt,
            max_turns=self.max_turns,
        )
        try:
            async for stream_event in self._run_result.stream_events():
                if event := map_sdk_event_to_agent_event(stream_event):
                    yield event
        finally:
            self._run_result = None

    async def cancel(self) -> None:
        """Cancel the currently executing turn, if any."""
        if self._run_result is not None:
            self._run_result.cancel()
        else:
            logger.warning("No active headless run to cancel")
