# ruff: noqa: PLC0415
"""Minimal unit tests for the AsyncAgent class.

These tests focus on a very narrow happy-path and a cancel path so that we
exercise the public behaviour of the agent without spinning up real MCP
servers or hitting the network.  External dependencies are stubbed via
fixtures to keep the test-code itself small and readable.  The goal is *not* to
re-implement every edge case – just to prove that the enqueue, streaming and
cancellation flows are wired up correctly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncGenerator, List
from unittest.mock import Mock

import pytest

from oai_coding_agent.agent.events import ToolCallEvent
from oai_coding_agent.runtime_config import ModeChoice, ModelChoice, RuntimeConfig

# ──────────────────────────────────────────────────────────────────────────────
# Helper / stub classes
# ──────────────────────────────────────────────────────────────────────────────


class _DummyRunResultStreaming:
    """A minimal stub that mimics the public surface used by AsyncAgent."""

    def __init__(self, stream_events: List[Any]):
        self._stream_events_data = stream_events
        self._cancelled = False
        self.cancel_called = False
        self.last_response_id = "dummy-id"

    async def stream_events(self) -> AsyncGenerator[Any, None]:  # pragma: no cover
        # First yield the pre-baked events …
        for ev in self._stream_events_data:
            yield ev
        # … then stay alive until *cancel()* is invoked so tests can poke at
        # mid-run state.
        while not self._cancelled:
            await asyncio.sleep(0.01)

    # The agent calls both ``cancel`` and ``to_input_list`` when a run is
    # interrupted mid-flight.
    def cancel(self) -> None:  # pragma: no cover
        self.cancel_called = True
        self._cancelled = True

    def to_input_list(self) -> List[str]:  # pragma: no cover
        return ["history"]


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def dummy_config(tmp_path: Path) -> RuntimeConfig:
    """Return a bare-bones *RuntimeConfig* that points at the temporary path."""

    return RuntimeConfig(
        openai_api_key="KEY",
        github_token=None,
        model=ModelChoice.codex_mini_latest,
        repo_path=tmp_path,
        mode=ModeChoice.default,
    )


@pytest.fixture()
def patch_async_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch heavy dependencies of *AsyncAgent* so the tests stay lightweight.

    We replace:
    * The background initialisation coroutine so that it does **not** spin up
      real MCP servers.
    * ``Runner.run_streamed`` so that no network calls are made.
    """

    # ------------------------------------------------------------------
    # 1. Patch *Runner.run_streamed* to return our dummy streaming result
    # ------------------------------------------------------------------
    import oai_coding_agent.agent.agent as agent_module

    def _fake_run_streamed(*_args: Any, **_kwargs: Any) -> _DummyRunResultStreaming:  # noqa: ANN401
        # We create a *Mock* that looks like a ``RunItemStreamEvent`` and will be
        # translated into a *ToolCallEvent* by the production mapping utility.
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

    # ------------------------------------------------------------------
    # 2. Avoid heavy background setup – drop straight to *ready* state.
    # ------------------------------------------------------------------
    async def _instant_init(self: agent_module.AsyncAgent) -> None:
        # Pretend everything initialised fine …
        self._openai_agent = SimpleNamespace()  # type: ignore[assignment]
        self._agent_ready_event.set()
        # … and then just wait until shutdown is requested.
        await self._shutdown_event.wait()

    monkeypatch.setattr(
        agent_module.AsyncAgent, "_initialize_in_background", _instant_init
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_agent_runs_and_emits_events(
    dummy_config: RuntimeConfig,
    patch_async_agent: None,  # fixture executes for its side-effects only
) -> None:
    """Happy-path: the agent accepts a prompt and puts mapped events on the queue."""

    from oai_coding_agent.agent.agent import AsyncAgent

    async with AsyncAgent(dummy_config, max_turns=5) as agent:
        # Enqueue a prompt for processing …
        await agent.run("What time is it?")

        # A single *ToolCallEvent* should appear on the public *events* queue.
        event = await asyncio.wait_for(agent.events.get(), timeout=1.0)
        assert isinstance(event, ToolCallEvent)
        assert event.name == "dummy_tool"
        assert event.arguments == "{}"

        # Make sure there are no further surprises pending.
        assert agent.events.empty()


@pytest.mark.asyncio
async def test_async_agent_cancel_flow(
    dummy_config: RuntimeConfig,
    patch_async_agent: None,
) -> None:
    """Calling *cancel()* mid-run should invoke *RunResult.cancel()* and set flags."""

    from oai_coding_agent.agent.agent import AsyncAgent

    async with AsyncAgent(dummy_config, max_turns=5) as agent:
        await agent.run("Start a long task")

        # Wait until the consumer created a *RunResultStreaming* instance …
        while agent._active_run_result is None:
            await asyncio.sleep(0.01)

        # Now cancel the turn.
        await agent.cancel()

        # The stubbed object records whether *cancel()* was called.
        rr = agent._active_run_result
        assert isinstance(rr, _DummyRunResultStreaming)
        assert rr.cancel_called is True

        # After cancellation the agent captures history for the next resume.
        assert agent._conversation_history == ["history"]

        # There should still be at least one event on the public queue.


@pytest.mark.asyncio
async def test_async_agent_max_turns_emits_error_event(
    dummy_config: RuntimeConfig,
    patch_async_agent: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When max turns is exceeded, emit an ErrorEvent and keep the consumer alive."""
    from agents import MaxTurnsExceeded, Runner

    from oai_coding_agent.agent.agent import AsyncAgent
    from oai_coding_agent.agent.events import ErrorEvent

    def fake_run_streamed(*args: Any, **kwargs: Any) -> Any:
        raise MaxTurnsExceeded("turn limit hit")

    monkeypatch.setattr(Runner, "run_streamed", fake_run_streamed)

    async with AsyncAgent(dummy_config, max_turns=1) as agent:
        await agent.run("dummy prompt")
        ev = await asyncio.wait_for(agent.events.get(), timeout=1.0)
        assert isinstance(ev, ErrorEvent)
        assert "turn limit hit" in ev.message
