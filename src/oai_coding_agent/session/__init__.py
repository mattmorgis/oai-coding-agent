"""Session tracking utilities for the OAI Coding Agent.

This package provides a small framework to:
- Generate a unique session ID per launch
- Append structured session metadata to a JSONL log in the XDG data dir
- Produce simple analytics (total sessions, last session timestamp)
"""

from .tracking import (
    generate_session_id,
    get_basic_stats,
    get_sessions_log_path,
    read_sessions,
    record_session,
)

__all__ = [
    "generate_session_id",
    "record_session",
    "read_sessions",
    "get_basic_stats",
    "get_sessions_log_path",
]
