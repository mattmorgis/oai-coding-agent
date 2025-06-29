"""
Logging configuration for oai_coding_agent CLI and internals.
"""

import logging

from concurrent_log_handler import ConcurrentRotatingFileHandler as RotatingFileHandler

from oai_coding_agent.xdg import get_data_dir


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure global logging:
      - Write all log records (including third-party libraries) to DATA_DIR/agent.log
      - Rotate the file at 10 MiB, keep 3 backups
      - Enable DEBUG for OpenAI SDK and HTTP requests
      - Silence overly verbose dependencies
    """
    log_dir = get_data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent.log"

    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s [%(levelname)s] %(message)s")
    )

    root = logging.root
    root.setLevel(level)
    root.addHandler(file_handler)

    # Set key loggers to the same level
    logging.getLogger("oai_coding_agent").setLevel(level)
    logging.getLogger("openai").setLevel(level)
    logging.getLogger("httpx").setLevel(level)
    logging.getLogger("urllib3").setLevel(level)

    # Silence overly verbose third-party modules
    for pkg in ("markdown_it", "httpcore", "asyncio"):
        logging.getLogger(pkg).setLevel(logging.WARNING)
