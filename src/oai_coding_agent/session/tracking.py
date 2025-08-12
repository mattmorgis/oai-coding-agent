"""
Basic session tracking for the OAI Coding Agent.

On each CLI launch, we generate a new session ID and append a record to a
JSON Lines (JSONL) log under the XDG data directory.

The log file path is: <XDG_DATA_HOME>/oai_coding_agent/sessions.jsonl
Each line is a JSON object with keys:
- session_id: str (UUID4)
- timestamp: str (ISO 8601, UTC)
- repo_path: str
- github_repo: Optional[str]
- branch_name: Optional[str]
- version: Optional[str]
- pid: Optional[int]

Additionally, simple analytics are provided to report total sessions and
last session timestamp.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from oai_coding_agent.xdg import get_data_dir

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    timestamp: str
    repo_path: str
    github_repo: Optional[str]
    branch_name: Optional[str]
    version: Optional[str]
    pid: Optional[int]


def get_sessions_log_path() -> Path:
    """Return the path to the sessions JSONL log in the XDG data dir."""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "sessions.jsonl"


def generate_session_id() -> str:
    """Generate a new UUID4 session ID as a string."""
    return str(uuid4())


def _utc_now_iso8601() -> str:
    return datetime.now(tz=UTC).isoformat()


def record_session(
    repo_path: Path,
    github_repo: Optional[str] = None,
    branch_name: Optional[str] = None,
    *,
    version: Optional[str] = None,
    now_ts: Optional[str] = None,
    pid: Optional[int] = None,
) -> str:
    """Create a session record and append it to the sessions log.

    Args:
        repo_path: Path to the active repository root.
        github_repo: Optional GitHub repo in "owner/repo" form.
        branch_name: Optional branch name.
        version: Optional application version string.
        now_ts: Optional ISO8601 timestamp override (UTC) for testing.
        pid: Optional process ID; defaults to os.getpid().

    Returns:
        The generated session_id as a string.
    """
    session_id = generate_session_id()
    timestamp = now_ts or _utc_now_iso8601()
    if pid is None:
        pid = os.getpid()

    record = SessionRecord(
        session_id=session_id,
        timestamp=timestamp,
        repo_path=str(repo_path),
        github_repo=github_repo,
        branch_name=branch_name,
        version=version,
        pid=pid,
    )

    log_path = get_sessions_log_path()
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    except Exception as e:
        # Don't crash the app for telemetry failures; just warn
        logger.warning("Failed to append session record: %s", e)

    logger.info("Started session %s for repo %s", session_id, repo_path)
    return session_id


def read_sessions() -> list[dict[str, Any]]:
    """Read all session entries from the JSONL log.

    Returns an empty list if the log does not exist or cannot be read.
    """
    log_path = get_sessions_log_path()
    if not log_path.exists():
        return []

    sessions: list[dict[str, Any]] = []
    try:
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    sessions.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue
    except Exception as e:
        logger.warning("Failed to read sessions log: %s", e)
        return []
    return sessions


def get_basic_stats() -> tuple[int, Optional[str]]:
    """Return (total_sessions, last_session_timestamp).

    If there are no records, returns (0, None).
    """
    sessions = read_sessions()
    if not sessions:
        return 0, None

    total = len(sessions)
    # Timestamps are in ISO8601; max will yield the latest
    timestamps: list[str] = []
    for s in sessions:
        if isinstance(s, dict):
            ts = s.get("timestamp")
            if isinstance(ts, str):
                timestamps.append(ts)
    last_ts: Optional[str] = max(timestamps) if timestamps else None
    return total, last_ts
