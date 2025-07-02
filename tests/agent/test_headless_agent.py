# ruff: noqa: PLC0415
"""Minimal unit tests for the HeadlessAgent class.

These tests focus on the happy-path and cancellation flows without
spinning up real MCP servers or hitting the network. External dependencies
are stubbed via fixtures to keep test-code small and readable.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncGenerator, List
from unittest.mock import Mock

import pytest

from oai_coding_agent.agent.agent import AgentInitializationError, HeadlessAgent
from oai_coding_agent.agent.events import ToolCallEvent
from oai_coding_agent.runtime_config import ModeChoice, ModelChoice, RuntimeConfig

# ──────────────────────────────────────────────────────────────────────────────
# Helper / stub classes
# ──────────────────────────────────────────────────────────────────────────────


class _DummyRunResultStreaming:
    """A minimal stub that mimics the public surface used by HeadlessAgent."""

    def __init__(self, stream_events: List[Any]) -> None:
        self._stream_events_data = stream_events
        self._cancelled = False
        self.cancel_called = False

    async def stream_events(self) -> AsyncGenerator[Any, None]:  # pragma: no cover
        for ev in self._stream_events_data:
            yield ev
        # Only keep alive if we have no events (for cancellation tests)
        if not self._stream_events_data:
            while not self._cancelled:
                await asyncio.sleep(0.01)

    def cancel(self) -> None:  # pragma: no cover
        self.cancel_called = True
        self._cancelled = True


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def dummy_config(tmp_path: Path) -> RuntimeConfig:
    """Return a bare-bones RuntimeConfig that points at the temporary path."""
    return RuntimeConfig(
        openai_api_key="KEY",
        github_token=None,
        model=ModelChoice.codex_mini_latest,
        repo_path=tmp_path,
        mode=ModeChoice.default,
    )


@pytest.fixture()
def patch_headless_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch heavy dependencies of HeadlessAgent so tests stay lightweight.

    We replace:
    * Runner.run_streamed to return our dummy streaming result.
    * start_mcp_servers, build_instructions, get_filtered_function_tools
    """
    import oai_coding_agent.agent.agent as agent_module

    def _fake_run_streamed(*_args: Any, **_kwargs: Any) -> _DummyRunResultStreaming:
        from agents import RunItemStreamEvent
        from agents.items import (  # type: ignore[attr-defined]
            ResponseFunctionToolCall,
            ToolCallItem,
        )

        rf = ResponseFunctionToolCall(
            name="dummy_tool",
            arguments="{}",
            call_id="cid",
            type="function_call",
        )
        tool_call_item = ToolCallItem(agent=Mock(), raw_item=rf)
        event = Mock(spec=RunItemStreamEvent)
        event.item = tool_call_item

        return _DummyRunResultStreaming([event])

    monkeypatch.setattr(agent_module.Runner, "run_streamed", _fake_run_streamed)  # type: ignore[attr-defined]

    async def _fake_start_mcp_servers(config: Any, stack: Any) -> SimpleNamespace:
        return SimpleNamespace()

    monkeypatch.setattr(agent_module, "start_mcp_servers", _fake_start_mcp_servers)
    monkeypatch.setattr(agent_module, "build_instructions", lambda config: [])

    async def _fake_get_filtered_function_tools(mcp: Any, config: Any) -> list[Any]:
        return []

    monkeypatch.setattr(
        agent_module,
        "get_filtered_function_tools",
        _fake_get_filtered_function_tools,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_headless_agent_cancel_invokes_cancel_on_run_result(
    dummy_config: RuntimeConfig,
    patch_headless_agent: None,
) -> None:
    """Cancelling while a run is in progress should call cancel() on the run result."""
    async with HeadlessAgent(dummy_config, max_turns=5) as agent:
        agen = agent.run("Work")
        # Start consuming the generator to initialize _run_result
        next_event: asyncio.Task[Any] = asyncio.create_task(agen.__anext__())  # type: ignore[arg-type]
        while agent._run_result is None:
            await asyncio.sleep(0.01)

        stub = agent._run_result
        assert isinstance(stub, _DummyRunResultStreaming)
        assert not stub.cancel_called

        await agent.cancel()
        assert stub.cancel_called is True

        # Clean up the pending task and generator
        with contextlib.suppress(Exception):
            await next_event
        await agen.aclose()


@pytest.mark.asyncio
async def test_headless_agent_run_without_context_raises(
    dummy_config: RuntimeConfig,
) -> None:
    """Calling run() without async context manager should raise initialization error."""
    agent = HeadlessAgent(dummy_config, max_turns=1)
    agen = agent.run("prompt")
    with pytest.raises(AgentInitializationError):
        await agen.__anext__()


@pytest.mark.asyncio
async def test_headless_agent_runs_and_yields_events(
    dummy_config: RuntimeConfig,
    patch_headless_agent: None,
) -> None:
    """Happy-path: run() yields mapped events and resets internal run_result."""
    async with HeadlessAgent(dummy_config, max_turns=5) as agent:
        events = [ev async for ev in agent.run("Hello")]
        assert len(events) == 1
        ev = events[0]
        assert isinstance(ev, ToolCallEvent)
        assert ev.name == "dummy_tool"
        assert ev.arguments == "{}"
        assert agent._run_result is None


@pytest.mark.asyncio
async def test_headless_agent_cancel_without_active_run_is_noop(
    dummy_config: RuntimeConfig,
    patch_headless_agent: None,
) -> None:
    """Calling cancel() when no run is active should not error."""
    async with HeadlessAgent(dummy_config, max_turns=5) as agent:
        await agent.cancel()
