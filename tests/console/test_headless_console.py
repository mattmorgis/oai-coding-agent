from typing import Any, AsyncIterator, List, Optional

import pytest

import oai_coding_agent.console.console as console_mod
from oai_coding_agent.console.console import HeadlessConsole


class DummyConfig:
    def __init__(self, prompt: str) -> None:
        self.prompt: str = prompt


class DummyAgent:
    def __init__(self, config: DummyConfig, events: Optional[List[Any]] = None) -> None:
        self.config: DummyConfig = config
        self._events: List[Any] = events or []
        self.cancel_called: bool = False

    async def __aenter__(self) -> "DummyAgent":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...

    def run(self, prompt: str) -> AsyncIterator[Any]:
        async def _gen() -> AsyncIterator[Any]:
            for ev in self._events:
                yield ev

        return _gen()

    async def cancel(self) -> None:
        self.cancel_called = True


@pytest.mark.asyncio
async def test_run_raises_if_no_prompt() -> None:
    agent = DummyAgent(DummyConfig(prompt=""), events=[])
    headless = HeadlessConsole(agent)  # type: ignore[arg-type]
    with pytest.raises(ValueError) as excinfo:
        await headless.run()
    assert "Prompt is required for headless mode" in str(excinfo.value)


@pytest.mark.asyncio
async def test_run_prints_prompt_and_renders_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: List[Any] = ["event1", "event2"]
    agent = DummyAgent(DummyConfig(prompt="test prompt"), events=events)
    headless = HeadlessConsole(agent)  # type: ignore[arg-type]

    printed: List[str] = []

    class FakeConsole:
        def print(self, msg: str) -> None:
            printed.append(msg)

    monkeypatch.setattr(console_mod, "console", FakeConsole())
    rendered: List[Any] = []
    monkeypatch.setattr(console_mod, "render_event", lambda ev: rendered.append(ev))

    await headless.run()

    assert printed == ["[bold cyan]Prompt:[/bold cyan] test prompt"]
    assert rendered == events


@pytest.mark.asyncio
async def test_run_cancel_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InterruptAgent(DummyAgent):
        def __init__(self, config: DummyConfig) -> None:
            super().__init__(config, events=[])

        def run(self, prompt: str) -> AsyncIterator[Any]:
            async def _gen() -> AsyncIterator[Any]:
                raise KeyboardInterrupt
                yield  # pragma: no cover

            return _gen()

    agent = InterruptAgent(DummyConfig(prompt="hi"))
    headless = HeadlessConsole(agent)  # type: ignore[arg-type]

    printed: List[str] = []

    class FakeConsole:
        def print(self, msg: str) -> None:
            printed.append(msg)

    monkeypatch.setattr(console_mod, "console", FakeConsole())
    monkeypatch.setattr(console_mod, "render_event", lambda ev: None)

    with pytest.raises(KeyboardInterrupt):
        await headless.run()

    assert agent.cancel_called
