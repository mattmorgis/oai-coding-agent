from pathlib import Path

import pytest

from oai_coding_agent.console.repl_console import ReplConsole
from oai_coding_agent.runtime_config import ModeChoice, ModelChoice, RuntimeConfig


class DummyAgent:
    """Minimal agent stub for testing ReplConsole prompt_fragments."""

    def __init__(
        self, is_processing: bool, config: RuntimeConfig | None = None
    ) -> None:
        self.is_processing = is_processing
        self.config = config or RuntimeConfig(
            openai_api_key="test-key",
            github_token=None,
            model=ModelChoice.codex_mini_latest,
            repo_path=Path("/tmp"),
            mode=ModeChoice.default,
        )


def test_prompt_fragments_full_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that prompt_fragments returns the full list of style/text fragments when processing.
    """
    agent = DummyAgent(is_processing=True)
    rc = ReplConsole(agent)  # type: ignore[arg-type]

    # Fix spinner and word cycler values for predictability
    monkeypatch.setattr(rc._spinner, "_current_frame", "X")
    monkeypatch.setattr(rc._word_cycler, "_current_word", "WORD")

    # Set token animator values
    rc._token_animator._current_input_val = 1500.0
    rc._token_animator._current_output_val = 2500.0

    fragments = list(rc.prompt_fragments())
    assert fragments == [
        ("", " "),
        ("ansicyan", "X"),
        ("italic", " WORD"),
        ("", " " * 28),
        ("ansiyellow", "[1.5k↑/2.5k↓]"),
        ("", " "),
        ("dim", "    ("),
        ("dim bold", "esc "),
        ("dim", "to interrupt)\n\n"),
        ("ansicyan", "› "),
    ]
