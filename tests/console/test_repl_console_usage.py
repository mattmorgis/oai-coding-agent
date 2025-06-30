import asyncio
from pathlib import Path
from typing import Any, Callable

import pytest
from conftest import MockAgent
from pytest import MonkeyPatch

import oai_coding_agent.console.repl_console as repl_mod
from oai_coding_agent.agent.events import ErrorEvent, UsageEvent
from oai_coding_agent.console.repl_console import ReplConsole
from oai_coding_agent.runtime_config import ModeChoice, ModelChoice, RuntimeConfig


@pytest.mark.asyncio
async def test_repl_console_usage_accumulates(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """
    Test that ReplConsole intercepts UsageEvent and maintains cumulative usage state,
    without rendering UsageEvent to the terminal.
    """

    # Monkey-patch run_in_terminal and render_event to avoid actual terminal I/O
    async def dummy_run_in_terminal(func: Callable[[], Any]) -> None:
        func()

    monkeypatch.setattr(repl_mod, "run_in_terminal", dummy_run_in_terminal)
    monkeypatch.setattr(repl_mod, "render_event", lambda event: None)

    # Initialize console with a mock agent
    config = RuntimeConfig(
        openai_api_key="APIKEY",
        github_token="GHTOKEN",
        model=ModelChoice.codex_mini_latest,
        repo_path=tmp_path,
        mode=ModeChoice.default,
    )
    agent = MockAgent(config)
    console = ReplConsole(agent)

    # Prepare multiple UsageEvent instances with varying token counts
    events = [
        UsageEvent(
            input_tokens=1,
            cached_input_tokens=2,
            output_tokens=3,
            reasoning_output_tokens=4,
            total_tokens=10,
        ),
        UsageEvent(
            input_tokens=5,
            cached_input_tokens=6,
            output_tokens=7,
            reasoning_output_tokens=8,
            total_tokens=26,
        ),
    ]

    # Enqueue usage events
    for ev in events:
        await agent.events.put(ev)

    # Enqueue a sentinel non-UsageEvent to advance the loop past UsageEvents
    sentinel = ErrorEvent("sentinel")
    await agent.events.put(sentinel)

    # Start the event stream consumer
    consumer_task = asyncio.create_task(console._event_stream_consumer())
    # Allow the consumer to process the queued events
    await asyncio.sleep(0.01)

    # Cancel the consumer task to exit the infinite loop
    consumer_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer_task

    # Verify that the console accumulated usage correctly
    assert console._usage_state.input_tokens == 6
    assert console._usage_state.cached_input_tokens == 8
    assert console._usage_state.output_tokens == 10
    assert console._usage_state.reasoning_output_tokens == 12
    assert console._usage_state.total_tokens == 36
