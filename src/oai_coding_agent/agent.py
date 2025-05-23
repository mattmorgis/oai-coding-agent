import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Optional

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
from openai.types.shared.reasoning import Reasoning

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

    _server_ctx: Optional[MCPServerStdio] = field(init=False, default=None)
    _server: Optional[MCPServerStdio] = field(init=False, default=None)
    _agent: Optional[Agent] = field(init=False, default=None)
    _trace_ctx: Optional[Trace] = field(init=False, default=None)

    async def __aenter__(self) -> "AgentSession":
        # Ensure API key is set
        os.environ["OPENAI_API_KEY"] = self.openai_api_key

        # Start the MCP filesystem server
        self._server_ctx = MCPServerStdio(
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

        # Begin tracing
        trace_id = gen_trace_id()
        self._trace_ctx = trace(workflow_name="OAI Coding Agent", trace_id=trace_id)
        self._trace_ctx.__enter__()

        # Build a dynamic system prompt that includes the repo path for extra context
        dynamic_instructions = (
            f"{INSTRUCTIONS}\n\n"
            f"The repository root path you can access is: {self.repo_path}\n"
        )

        # Instantiate the agent
        self._agent = Agent(
            name="Coding Agent",
            instructions=dynamic_instructions,
            model=self.model,
            model_settings=ModelSettings(
                reasoning=Reasoning(summary="auto", effort="high")
            ),
            mcp_servers=[self._server],
        )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # End tracing and shut down server
        if self._trace_ctx:
            self._trace_ctx.__exit__(exc_type, exc_val, exc_tb)
        if self._server_ctx:
            await self._server_ctx.__aexit__(exc_type, exc_val, exc_tb)

    async def run_step(
        self,
        user_input: str,
        previous_response_id: Optional[str] = None,
    ) -> tuple[AsyncIterator, RunResultStreaming]:
        """
        Send one user message to the agent and return an async iterator of events plus the result.

        Usage:
            events, result = await session.run_step(user_input, prev_id)
            async for event in events:
                handle event
            prev_id = result.last_response_id
        """
        result = Runner.run_streamed(
            self._agent,
            user_input,
            previous_response_id=previous_response_id,
            max_turns=self.max_turns,
        )
        return result.stream_events(), result
