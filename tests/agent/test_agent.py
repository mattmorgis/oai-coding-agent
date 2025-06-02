import os
from pathlib import Path
from typing import Any, AsyncGenerator, cast

import pytest
from agents import Agent as SDKAgent
from agents import Runner
from agents.mcp import MCPServerStdioParams

import oai_coding_agent.agent.mcp_servers as mcp_servers_module
from oai_coding_agent.agent.agent import Agent
from oai_coding_agent.agent.mcp_servers import (
    ALLOWED_CLI_COMMANDS,
    ALLOWED_CLI_FLAGS,
    QuietMCPServerStdio,
)
from oai_coding_agent.runtime_config import ModeChoice, ModelChoice, RuntimeConfig


def test_allowed_cli_vars() -> None:
    # Ensure allowed CLI commands and flags are defined as lists and contain expected values
    assert isinstance(ALLOWED_CLI_COMMANDS, list)
    assert "grep" in ALLOWED_CLI_COMMANDS
    assert isinstance(ALLOWED_CLI_FLAGS, list)
    assert "all" in ALLOWED_CLI_FLAGS


def test_quiet_mcp_server_stdio_create_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    # Monkeypatch stdio_client to capture params and errlog
    captured = {}

    def fake_stdio_client(params_arg: Any, errlog: Any | None = None) -> str:
        captured["params"] = params_arg
        captured["errlog"] = errlog
        return "fake_streams"

    monkeypatch.setattr(mcp_servers_module, "stdio_client", fake_stdio_client)

    params = {"command": "test", "args": []}
    quiet = QuietMCPServerStdio(
        name="test",
        params=cast(MCPServerStdioParams, params),
        client_session_timeout_seconds=10,
        cache_tools_list=False,
    )
    streams = quiet.create_streams()
    assert streams == "fake_streams"
    # Params should be passed through unchanged
    # Params should contain the correct command and args attributes
    param_obj = captured["params"]
    assert hasattr(param_obj, "command") and param_obj.command == "test"
    assert hasattr(param_obj, "args") and param_obj.args == []
    # errlog should be a file to os.devnull
    errlog = captured["errlog"]
    assert hasattr(errlog, "write")
    assert getattr(errlog, "name", None) == os.devnull
    # Close the errlog file
    errlog.close()


class DummyRaw:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class DummyItem:
    def __init__(self, raw_item: Any) -> None:
        self.raw_item = raw_item


class DummyEvent:
    def __init__(self, type: Any = None, name: Any = None, item: Any = None) -> None:
        self.type = type
        self.name = name
        self.item = item


@pytest.mark.asyncio
async def test_run_streams_and_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    # Prepare dummy events in stream order
    events = [
        DummyEvent(
            type="run_item_stream_event",
            name="tool_called",
            item=DummyItem(DummyRaw(name="t", arguments=("x",))),
        ),
        DummyEvent(
            name="reasoning_item_created",
            item=DummyItem(DummyRaw(summary=[DummyRaw(text="r")])),
        ),
        DummyEvent(
            name="message_output_created",
            item=DummyItem(DummyRaw(content=[DummyRaw(text="m")])),
        ),
        DummyEvent(type="none", name="unknown", item=DummyItem(DummyRaw())),
    ]

    class FakeResult:
        def __init__(self, evts: list[Any]) -> None:
            self._events = evts

        def stream_events(self) -> AsyncGenerator[Any, None]:
            async def gen() -> AsyncGenerator[Any, None]:
                for e in self._events:
                    yield e

            return gen()

    fake_result = FakeResult(events)

    # Monkeypatch Runner.run_streamed
    monkeypatch.setattr(
        Runner,
        "run_streamed",
        lambda agent, u, previous_response_id, max_turns: fake_result,
    )
    # Initialize agent and set dummy SDK agent
    config = RuntimeConfig(
        openai_api_key="k",
        github_personal_access_token="TOK",
        model=ModelChoice.codex_mini_latest,
        repo_path=Path("."),
        mode=ModeChoice.async_,
    )
    agent = Agent(config, max_turns=1)
    agent._sdk_agent = cast(SDKAgent, object())

    ui_stream, returned = await agent.run("input text", previous_response_id="prev")
    # Should return the underlying result as is
    assert returned is fake_result  # type: ignore[comparison-overlap]
    # Collect messages from ui_stream
    collected = []
    async for msg in ui_stream:
        collected.append(msg)
    # Should map exactly three events (skip unknown)
    # Note: The actual event mapping is now tested in test_event_mapper.py
    assert len(collected) == 3
