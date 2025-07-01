from itertools import cycle as _cycle
from pathlib import Path

import pytest
from prompt_toolkit.formatted_text import to_plain_text

from oai_coding_agent.console.repl_console import ReplConsole, Spinner
from oai_coding_agent.runtime_config import ModeChoice, ModelChoice, RuntimeConfig


class DummyAgent:
    def __init__(
        self, is_processing: bool = False, config: RuntimeConfig | None = None
    ) -> None:
        self.is_processing = is_processing
        self.config = config or RuntimeConfig(
            openai_api_key="test-key",
            github_token=None,
            model=ModelChoice.codex_mini_latest,
            repo_path=Path("/tmp"),
            mode=ModeChoice.default,
        )


def test_prompt_fragments_idle() -> None:
    agent = DummyAgent(False)
    rc = ReplConsole(agent)  # type: ignore[arg-type]
    output = to_plain_text(rc.prompt_fragments())
    assert output == "\n\n› "


def test_prompt_fragments_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = DummyAgent(True)
    rc = ReplConsole(agent)  # type: ignore[arg-type]
    monkeypatch.setattr(rc._spinner, "_current_frame", "X")
    text = to_plain_text(rc.prompt_fragments())
    assert "X processing" in text
    assert "(esc to interrupt)" in text
    assert text.strip().endswith("›")


def test_spinner_update_cycles_frames() -> None:
    spinner = Spinner()
    # Override frames for predictability
    spinner._frames = ("A", "B", "C")  # type: ignore[assignment]
    spinner._cycle = _cycle(spinner._frames)
    spinner._current_frame = next(spinner._cycle)

    assert spinner.current_frame == "A"
    spinner.update()
    assert spinner.current_frame == "B"
    spinner.update()
    assert spinner.current_frame == "C"
    spinner.update()
    assert spinner.current_frame == "A"
