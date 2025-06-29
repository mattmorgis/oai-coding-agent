import asyncio
from itertools import cycle as _cycle

import pytest
from prompt_toolkit.formatted_text import to_plain_text

from oai_coding_agent.console.repl_console import ReplConsole, Spinner


class DummyAgent:
    def __init__(self, is_processing: bool = False) -> None:
        self.is_processing = is_processing


def test_prompt_fragments_idle() -> None:
    agent = DummyAgent(False)
    rc = ReplConsole(agent)  # type: ignore[arg-type]
    output = to_plain_text(rc.prompt_fragments())
    assert output == "\n› "


def test_prompt_fragments_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = DummyAgent(True)
    rc = ReplConsole(agent)  # type: ignore[arg-type]
    monkeypatch.setattr(rc._spinner, "_current_frame", "X")
    text = to_plain_text(rc.prompt_fragments())
    assert "X thinking..." in text
    assert "(ESC" in text
    assert text.strip().endswith("›")


@pytest.mark.asyncio
async def test_spinner_self_ticking(monkeypatch: pytest.MonkeyPatch) -> None:
    spinner = Spinner(interval=0)
    spinner._frames = ("A", "B", "C")  # type: ignore[assignment]
    spinner._cycle = _cycle(spinner._frames)
    spinner._current_frame = next(spinner._cycle)

    async def dummy_sleep(_: float) -> None:
        return

    monkeypatch.setattr(asyncio, "sleep", dummy_sleep)

    spinner.start()
    await asyncio.sleep(0)
    assert spinner.current_frame == "B"
    spinner.stop()
