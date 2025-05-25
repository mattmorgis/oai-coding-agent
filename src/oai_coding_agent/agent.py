import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from agents import (
    Agent,
    ModelSettings,
    Runner,
    RunResultStreaming,
    Trace,
    gen_trace_id,
    trace,
)
from agents.mcp import MCPServerStdio
from mcp.client.stdio import stdio_client
from openai.types.shared.reasoning import Reasoning

logger = logging.getLogger(__name__)


class QuietMCPServerStdio(MCPServerStdio):
    """Variant of MCPServerStdio that silences child‐process stderr."""

    def create_streams(self):
        # Redirect any console.err from the server process into the void
        return stdio_client(self.params, errlog=open(os.devnull, "w"))


# Instructions for the agent's behavior in the codebase
INSTRUCTIONS = (
    "You are a helpful agent that can answer questions and help with tasks. "
    "Use the tools to navigate and read the codebase, and answer questions based on those files. "
    "When exploring repositories, avoid using directory_tree on the root directory. "
    "Instead, use list_directory to explore one level at a time and search_files to find relevant files matching patterns. "
    "If you need to understand a specific subdirectory structure, use directory_tree only on that targeted directory."
)


@dataclass
class AgentSession:
    """Manage a long-lived agent session for streaming responses."""

    repo_path: Path
    model: str
    openai_api_key: str
    max_turns: int = 100

    _server_ctx: Optional[QuietMCPServerStdio] = field(init=False, default=None)
    _server: Optional[MCPServerStdio] = field(init=False, default=None)
    _cli_server_ctx: Optional[QuietMCPServerStdio] = field(init=False, default=None)
    _cli_server: Optional[MCPServerStdio] = field(init=False, default=None)
    _agent: Optional[Agent] = field(init=False, default=None)
    _trace_ctx: Optional[Trace] = field(init=False, default=None)

    async def __aenter__(self) -> "AgentSession":
        # Ensure API key is set
        os.environ["OPENAI_API_KEY"] = self.openai_api_key

        # Start the MCP filesystem server
        self._server_ctx = QuietMCPServerStdio(
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
        self._server = await self._server_ctx.__aenter__()

        # List to collect all MCP servers
        mcp_servers = [self._server]

        try:
            self._cli_server_ctx = QuietMCPServerStdio(
                name="cli-mcp-server",
                params={
                    "command": "cli-mcp-server",
                    "env": {
                        "ALLOWED_DIR": str(self.repo_path),
                        "ALLOWED_COMMANDS": "grep,rg,find,ls,cat,head,tail,wc,pwd,echo,sed,awk,sort,uniq,fzf,bat,git,uv,pip,pipdeptree,xargs,which",
                        "ALLOWED_FLAGS": "-r,-R,-n,-i,-v,-l,-c,-h,-H,-o,-E,-F,-w,-x,-e,-C,-P,-A,-B,-f,--filter,--help,--version,--context,--after-context,--before-context,--perl-regexp,--regexp,--line-number,--type",
                        "ALLOW_SHELL_OPERATORS": "true",
                        "COMMAND_TIMEOUT": "120",
                    },
                },
                client_session_timeout_seconds=120,
                cache_tools_list=True,
            )
            self._cli_server = await self._cli_server_ctx.__aenter__()
            mcp_servers.append(self._cli_server)
            logger.info("CLI MCP server started successfully")
        except Exception as e:
            logger.warning(f"Failed to start CLI MCP server: {e}")

        # Begin tracing
        trace_id = gen_trace_id()
        self._trace_ctx = trace(workflow_name="OAI Coding Agent", trace_id=trace_id)
        self._trace_ctx.__enter__()

        # Build a dynamic system prompt that includes the repo path for extra context
        dynamic_instructions = (
            f"{INSTRUCTIONS}\n\n"
            f"The repository root path you can access is: {self.repo_path}\n"
        )

        # Add grep instructions if CLI tools are available
        if len(mcp_servers) > 1:
            dynamic_instructions += (
                "\nYou also have access to CLI tools including grep for powerful text searching. "
                "Use 'run_command' with grep or rg (ripgrep) for efficient code searching."
            )

        # Instantiate the agent
        self._agent = Agent(
            name="Coding Agent",
            instructions=dynamic_instructions,
            model=self.model,
            model_settings=ModelSettings(
                reasoning=Reasoning(summary="auto", effort="high")
            ),
            mcp_servers=mcp_servers,
        )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # End tracing and shut down servers
        if self._trace_ctx:
            self._trace_ctx.__exit__(exc_type, exc_val, exc_tb)
        if self._cli_server_ctx:
            await self._cli_server_ctx.__aexit__(exc_type, exc_val, exc_tb)
        if self._server_ctx:
            await self._server_ctx.__aexit__(exc_type, exc_val, exc_tb)

    def _map_sdk_event(self, event) -> Optional[Dict[str, Any]]:
        """Translate low-level SDK stream events into high-level UI messages."""
        evt_type = getattr(event, "type", None)
        evt_name = getattr(event, "name", None)
        logger.debug(
            f"SDK event received: type={evt_type}, name={evt_name}, event={event!r}"
        )

        # Tool calls
        if evt_type == "run_item_stream_event" and evt_name == "tool_called":
            return {
                "role": "tool",
                "content": f"{event.item.raw_item.name}({event.item.raw_item.arguments})",
            }
        # Reasoning items (thoughts)
        if evt_name == "reasoning_item_created":
            summary = event.item.raw_item.summary
            if summary:
                text = summary[0].text
                return {"role": "thought", "content": f"💭 {text}"}
        # Assistant messages
        if evt_name == "message_output_created":
            return {
                "role": "assistant",
                "content": event.item.raw_item.content[0].text,
            }
        return None  # ignore everything else

    async def run_step(
        self,
        user_input: str,
        previous_response_id: Optional[str] = None,
    ) -> tuple[AsyncIterator[Dict[str, Any]], RunResultStreaming]:
        """
        Send one user message to the agent and return an async iterator of *UI
        messages* plus the underlying RunResultStreaming.
        """
        # Kick off the streamed run in the SDK.
        result = Runner.run_streamed(
            self._agent,
            user_input,
            previous_response_id=previous_response_id,
            max_turns=self.max_turns,
        )
        sdk_events = result.stream_events()

        # We produce an async generator that merges retry notifications and
        # mapped SDK events.
        async def _ui_stream() -> AsyncIterator[Dict[str, Any]]:
            # Iterate over SDK events; after each one flush any queued retry msgs.
            async for evt in sdk_events:
                # # Yield any retry notifications waiting.
                # while not self._retry_queue.empty():
                #     yield await self._retry_queue.get()

                msg = self._map_sdk_event(evt)
                if msg:
                    yield msg

            # # After SDK stream ends, drain any remaining retry messages.
            # while not self._retry_queue.empty():
            #     yield await self._retry_queue.get()

        return _ui_stream(), result
