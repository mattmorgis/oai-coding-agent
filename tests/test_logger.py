import logging
from pathlib import Path

import pytest

from oai_coding_agent.logger import setup_logging
from oai_coding_agent.xdg import get_data_dir


def test_setup_logging_creates_log_dir_and_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Monkeypatch home directory
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Capture original handlers to restore later
    root = logging.root
    orig_handlers = list(root.handlers)

    # Ensure no OPENAI log directory exists yet
    log_dir = get_data_dir()
    assert not log_dir.exists()

    try:
        setup_logging(level=logging.DEBUG)
        # Emit a log message to ensure handler writes the file
        logging.getLogger().debug("test log entry")
        # Directory and file should be created
        assert log_dir.is_dir()
        log_file = log_dir / "agent.log"
        assert log_file.exists(), "Log file should be created by handler"

        # Root logger level should be set to DEBUG
        assert root.level == logging.DEBUG

        # A new handler should have been added
        new_handlers = [h for h in root.handlers if h not in orig_handlers]
        assert len(new_handlers) == 1

        # Ensure other specific loggers are set to DEBUG or higher
        assert logging.getLogger("oai_coding_agent").level == logging.DEBUG
        assert logging.getLogger("openai").level == logging.DEBUG
        assert logging.getLogger("httpx").level == logging.DEBUG
        assert logging.getLogger("urllib3").level == logging.DEBUG

        # Overly verbose packages are silenced to WARNING level
        for pkg in ("markdown_it", "httpcore", "asyncio"):
            assert logging.getLogger(pkg).level == logging.WARNING
    finally:
        # Clean up handlers to original state
        for h in root.handlers[:]:
            if h not in orig_handlers:
                root.removeHandler(h)
        # Restore original handlers
        root.handlers = orig_handlers
