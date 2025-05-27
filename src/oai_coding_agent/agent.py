"""
AgentSession context manager for streaming OAI agent interactions with a local codebase.
"""

import logging
import os
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from agents import (
    Agent,
    ModelSettings,
    Runner,
    RunResultStreaming,
    gen_trace_id,
    trace,
)
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from openai.types.shared.reasoning import Reasoning

from .mcp_servers import start_mcp_servers
from .mcp_tool_selector import get_filtered_function_tools

logger = logging.getLogger(__name__)

TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=False,
    keep_trailing_newline=True,
)


_DEFAULT_MODE = "default"


@dataclass
class _AgentSession:
    """Internal agent session managing MCP servers, tracing, and the Agent instance."""

    repo_path: Path
    model: str
    openai_api_key: str
    github_personal_access_token: str
    max_turns: int = 100
    mode: str = _DEFAULT_MODE

    _exit_stack: AsyncExitStack = field(init=False, repr=False)
    _agent: Agent = field(init=False, repr=False)

    async def _startup(self) -> None:
        # Initialize exit stack for async contexts and callbacks
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        # Ensure API key is set for OpenAI SDK
        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        # Ensure GitHub token is set for GitHub MCP server
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = self.github_personal_access_token

        # Start MCP servers (filesystem, CLI, Git, GitHub) and register cleanup
        mcp_servers = await start_mcp_servers(self.repo_path, self._exit_stack)

        # Begin tracing
        trace_id = gen_trace_id()
        trace_ctx = trace(workflow_name="OAI Coding Agent", trace_id=trace_id)
        trace_ctx.__enter__()
        self._exit_stack.callback(trace_ctx.__exit__, None, None, None)

        # Build instructions and fetch filtered MCP function-tools
        dynamic_instructions = self._build_instructions()
        function_tools = await get_filtered_function_tools(mcp_servers, self.mode)

        # Include the OpenAI Code Interpreter built-in tool alongside filtered function-tools
        tools = [{"type": "code_interpreter"}, *function_tools]
        self._agent = Agent(
            name="Coding Agent",
            instructions=dynamic_instructions,
            model=self.model,
            model_settings=ModelSettings(
                reasoning=Reasoning(summary="auto", effort="high")
            ),
            tools=tools,
        )

    async def _cleanup(self) -> None:
        await self._exit_stack.__aexit__(None, None, None)

    def _build_instructions(self) -> str:
        try:
            template = TEMPLATE_ENV.get_template(f"prompt_{self.mode}.jinja2")
        except TemplateNotFound:
            template = TEMPLATE_ENV.get_template("prompt_default.jinja2")
        return template.render(repo_path=str(self.repo_path), mode=self.mode)

    def _map_sdk_event(self, event: Any) -> Optional[Dict[str, Any]]:
        evt_type = getattr(event, "type", None)
        evt_name = getattr(event, "name", None)
        logger.debug(
            "SDK event received: type=%s, name=%s, event=%r", evt_type, evt_name, event
        )

        if evt_type == "run_item_stream_event" and evt_name == "tool_called":
            return {
                "role": "tool",
                "content": f"{event.item.raw_item.name}({event.item.raw_item.arguments})",
            }
        if evt_name == "reasoning_item_created":
            summary = event.item.raw_item.summary
            if summary:
                text = summary[0].text
                return {"role": "thought", "content": f"💭 {text}"}
        if evt_name == "message_output_created":
            return {
                "role": "assistant",
                "content": event.item.raw_item.content[0].text,
            }
        return None

    async def run_step(
        self,
        user_input: str,
        previous_response_id: Optional[str] = None,
    ) -> tuple[AsyncIterator[Dict[str, Any]], RunResultStreaming]:
        """
        Send one user message to the agent and return an async iterator of UI messages
        plus the underlying RunResultStreaming.
        """
        result = Runner.run_streamed(
            self._agent,
            user_input,
            previous_response_id=previous_response_id,
            max_turns=self.max_turns,
        )
        sdk_events = result.stream_events()

        async def _ui_stream() -> AsyncIterator[Dict[str, Any]]:
            async for evt in sdk_events:
                msg = self._map_sdk_event(evt)
                if msg:
                    yield msg

        return _ui_stream(), result


@asynccontextmanager
async def AgentSession(
    repo_path: Path,
    model: str,
    openai_api_key: str,
    github_personal_access_token: str,
    max_turns: int = 100,
    mode: str = _DEFAULT_MODE,
) -> AsyncIterator[_AgentSession]:
    """
    Async context manager for setting up and tearing down an agent session.
    """
    session = _AgentSession(
        repo_path=repo_path,
        model=model,
        openai_api_key=openai_api_key,
        github_personal_access_token=github_personal_access_token,
        max_turns=max_turns,
        mode=mode,
    )
    await session._startup()
    try:
        yield session
    finally:
        await session._cleanup()
