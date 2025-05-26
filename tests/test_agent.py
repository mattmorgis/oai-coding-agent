import os
import pytest
import asyncio
from pathlib import Path

import oai_coding_agent.agent as agent_module
from oai_coding_agent.agent import (
    _AgentSession,
    QuietMCPServerStdio,
    ALLOWED_CLI_COMMANDS,
    ALLOWED_CLI_FLAGS,
)


def test_allowed_cli_vars():
    # Ensure allowed CLI commands and flags are defined as lists and contain expected values
    assert isinstance(ALLOWED_CLI_COMMANDS, list)
    assert "grep" in ALLOWED_CLI_COMMANDS
    assert isinstance(ALLOWED_CLI_FLAGS, list)
    assert "all" in ALLOWED_CLI_FLAGS


def test_quiet_mcp_server_stdio_create_streams(monkeypatch):
    # Monkeypatch stdio_client to capture params and errlog
    captured = {}

    def fake_stdio_client(params_arg, errlog=None):
        captured["params"] = params_arg
        captured["errlog"] = errlog
        return "fake_streams"

    monkeypatch.setattr(agent_module, "stdio_client", fake_stdio_client)

    params = {"command": "test", "args": []}
    quiet = QuietMCPServerStdio(
        name="test",
        params=params,
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


def test_build_instructions_with_known_mode():
    session = _AgentSession(
        repo_path=Path("repo"),
        model="model-x",
        openai_api_key="apikey",
        max_turns=5,
        mode="async",
    )
    instr = session._build_instructions()
    # Should load prompt_async.jinja2
    assert instr.startswith(
        "You are an autonomous software engineering agent running in GitHub Actions"
    )
    # Should not be empty
    assert "## Autonomous Decision Making" in instr


def test_build_instructions_with_unknown_mode_fallback():
    session = _AgentSession(
        repo_path=Path("repo2"),
        model="model-y",
        openai_api_key="apikey",
        max_turns=5,
        mode="nonexistent_mode",
    )
    instr = session._build_instructions()
    # Should fallback to default prompt
    assert instr.startswith(
        "You are OAI - a collaborative software engineering assistant"
    )
    assert "## Collaborative Approach" in instr


class DummyRaw:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class DummyItem:
    def __init__(self, raw_item):
        self.raw_item = raw_item


class DummyEvent:
    def __init__(self, type=None, name=None, item=None):
        self.type = type
        self.name = name
        self.item = item


def test_map_sdk_event_tool():
    raw = DummyRaw(name="cmd", arguments=("a", "b"))
    event = DummyEvent(
        type="run_item_stream_event", name="tool_called", item=DummyItem(raw)
    )
    mapped = agent_module._AgentSession._map_sdk_event(None, event)
    assert mapped == {"role": "tool", "content": "cmd(('a', 'b'))"}


def test_map_sdk_event_reasoning_with_summary():
    raw = DummyRaw(summary=[DummyRaw(text="thinking")])
    event = DummyEvent(name="reasoning_item_created", item=DummyItem(raw))
    mapped = agent_module._AgentSession._map_sdk_event(None, event)
    assert mapped == {"role": "thought", "content": "💭 thinking"}


def test_map_sdk_event_reasoning_without_summary():
    raw = DummyRaw(summary=[])
    event = DummyEvent(name="reasoning_item_created", item=DummyItem(raw))
    mapped = agent_module._AgentSession._map_sdk_event(None, event)
    assert mapped is None


def test_map_sdk_event_message_output_created():
    raw = DummyRaw(content=[DummyRaw(text="output text")])
    event = DummyEvent(name="message_output_created", item=DummyItem(raw))
    mapped = agent_module._AgentSession._map_sdk_event(None, event)
    assert mapped == {"role": "assistant", "content": "output text"}


def test_map_sdk_event_other():
    event = DummyEvent(type="other", name="something_else", item=DummyItem(DummyRaw()))
    mapped = agent_module._AgentSession._map_sdk_event(None, event)
    assert mapped is None


@pytest.mark.asyncio
async def test_run_step_streams_and_returns(monkeypatch):
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
        def __init__(self, evts):
            self._events = evts

        def stream_events(self):
            async def gen():
                for e in self._events:
                    yield e

            return gen()

    fake_result = FakeResult(events)

    # Monkeypatch Runner.run_streamed
    monkeypatch.setattr(
        agent_module.Runner,
        "run_streamed",
        lambda agent, u, previous_response_id, max_turns: fake_result,
    )
    # Initialize session and set dummy agent
    session = _AgentSession(
        repo_path=Path("."), model="m", openai_api_key="k", max_turns=1, mode="async"
    )
    session._agent = object()

    ui_stream, returned = await session.run_step(
        "input text", previous_response_id="prev"
    )
    # Should return the underlying result as is
    assert returned is fake_result
    # Collect messages from ui_stream
    collected = []
    async for msg in ui_stream:
        collected.append(msg)
    # Should map exactly three events (skip unknown)
    assert collected == [
        {"role": "tool", "content": "t(('x',))"},
        {"role": "thought", "content": "💭 r"},
        {"role": "assistant", "content": "m"},
    ]
