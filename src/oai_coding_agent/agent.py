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
from agents.mcp import MCPServerStdio
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from mcp.client.stdio import stdio_client
from openai.types.shared.reasoning import Reasoning

logger = logging.getLogger(__name__)

TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=False,
    keep_trailing_newline=True,
)

ALLOWED_CLI_COMMANDS = [
    "grep",
    "rg",
    "find",
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "pwd",
    "echo",
    "sed",
    "awk",
    "sort",
    "uniq",
    "fzf",
    "bat",
    "git",
    "uv",
    "pip",
    "pipdeptree",
    "xargs",
    "which",
]

ALLOWED_CLI_FLAGS = ["all"]

_DEFAULT_MODE = "async"


class QuietMCPServerStdio(MCPServerStdio):
    """Variant of MCPServerStdio that silences child-process stderr."""

    def create_streams(self):
        return stdio_client(self.params, errlog=open(os.devnull, "w"))


@dataclass
class _AgentSession:
    """Internal agent session managing MCP servers, tracing, and the Agent instance."""

    repo_path: Path
    model: str
    openai_api_key: str
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

        # Start filesystem MCP server
        fs_ctx = QuietMCPServerStdio(
            name="file-system-mcp",
            params={
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    str(self.repo_path),
                ],
            },
            client_session_timeout_seconds=30,
            cache_tools_list=True,
        )
        fs_server = await fs_ctx.__aenter__()
        self._exit_stack.push_async_callback(fs_ctx.__aexit__, None, None, None)
        mcp_servers = [fs_server]

        # Attempt to start CLI MCP server
        try:
            cli_ctx = QuietMCPServerStdio(
                name="cli-mcp-server",
                params={
                    "command": "cli-mcp-server",
                    "env": {
                        "ALLOWED_DIR": str(self.repo_path),
                        "ALLOWED_COMMANDS": ",".join(ALLOWED_CLI_COMMANDS),
                        "ALLOWED_FLAGS": ",".join(ALLOWED_CLI_FLAGS),
                        "ALLOW_SHELL_OPERATORS": "true",
                        "COMMAND_TIMEOUT": "120",
                    },
                },
                client_session_timeout_seconds=120,
                cache_tools_list=True,
            )
            cli_server = await cli_ctx.__aenter__()
            self._exit_stack.push_async_callback(cli_ctx.__aexit__, None, None, None)
            mcp_servers.append(cli_server)
            logger.info("CLI MCP server started successfully")
        except OSError:
            logger.exception("Failed to start CLI MCP server")

        # Attempt to start Git MCP server
        try:
            git_ctx = QuietMCPServerStdio(
                name="mcp-server-git",
                params={
                    "command": "mcp-server-git",
                },
                client_session_timeout_seconds=120,
                cache_tools_list=True,
            )
            git_server = await git_ctx.__aenter__()
            self._exit_stack.push_async_callback(git_ctx.__aexit__, None, None, None)
            mcp_servers.append(git_server)
            logger.info("Git MCP server started successfully")
        except OSError:
            logger.exception("Failed to start Git MCP server")

        # Begin tracing
        trace_id = gen_trace_id()
        trace_ctx = trace(workflow_name="OAI Coding Agent", trace_id=trace_id)
        trace_ctx.__enter__()
        self._exit_stack.callback(trace_ctx.__exit__, None, None, None)

        # Build instructions and instantiate the Agent
        dynamic_instructions = self._build_instructions()
        self._agent = Agent(
            name="Coding Agent",
            instructions=dynamic_instructions,
            model=self.model,
            model_settings=ModelSettings(
                reasoning=Reasoning(summary="auto", effort="high")
            ),
            mcp_servers=mcp_servers,
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
        max_turns=max_turns,
        mode=mode,
    )
    await session._startup()
    try:
        yield session
    finally:
        await session._cleanup()
