"""
Session tracking for the OAI Coding Agent.

Responsibilities:
- Generate a UUIDv4 session ID per process launch
- Log session start and termination timestamps
- Persist session information to an append-only JSONL file in the XDG data dir
- Associate sessions with a stable, anonymized user identifier
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import signal
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from oai_coding_agent.xdg import get_data_dir

logger = logging.getLogger(__name__)


@dataclass
class SessionStartRecord:
    type: str
    session_id: str
    user_id: Optional[str]
    timestamp: str
    version: Optional[str] = None
    pid: Optional[int] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionEndRecord:
    type: str
    session_id: str
    user_id: Optional[str]
    timestamp: str
    duration_seconds: float
    reason: str = "exit"


class SessionTracker:
    """Track a single agent session lifecycle and persist analytics events."""

    def __init__(self, sessions_file: Optional[Path] = None) -> None:
        self._data_dir = get_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_file = sessions_file or (self._data_dir / "sessions.jsonl")
        self._user_id_file = self._data_dir / "user_id"

        self.session_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self._start_monotonic: Optional[float] = None
        self._ended = False
        self._lock = threading.Lock()

        # Ensure file exists
        self._sessions_file.touch(exist_ok=True)

    def get_or_create_anonymized_user_id(self) -> str:
        """Return a stable anonymized user identifier for analytics.

        We persist a random UUID in the data dir on first run and reuse it.
        """
        try:
            if self._user_id_file.exists():
                return self._user_id_file.read_text(encoding="utf-8").strip()
            # Generate and persist a new UUID
            new_id = str(uuid.uuid4())
            self._user_id_file.write_text(new_id, encoding="utf-8")
            return new_id
        except Exception:
            # Fail closed – if we can't persist, return an ephemeral id
            ephemeral = str(uuid.uuid4())
            logger.debug("Failed to persist user_id; using ephemeral id", exc_info=True)
            return ephemeral

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append_jsonl(self, obj: Any) -> None:
        try:
            with self._sessions_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        except Exception:
            logger.debug("Failed to write session record", exc_info=True)

    def start(
        self, version: Optional[str] = None, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Start a new session and write a start record to disk.

        Returns the generated session_id.
        """
        with self._lock:
            if self.session_id is not None:
                return self.session_id

            self.session_id = str(uuid.uuid4())
            self.user_id = self.get_or_create_anonymized_user_id()
            self._start_monotonic = time.monotonic()

            start_record = SessionStartRecord(
                type="session_start",
                session_id=self.session_id,
                user_id=self.user_id,
                timestamp=self._utc_now_iso(),
                version=version,
                pid=os.getpid(),
                context=context or {},
            )
            self._append_jsonl(asdict(start_record))
            logger.info("Session started: id=%s user=%s", self.session_id, self.user_id)

            # Register atexit handler to ensure end record is written
            atexit.register(self._atexit_end)

            # Best-effort signal handlers for clean termination
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    signal.signal(sig, self._signal_handler)
                except Exception:
                    # On some platforms (e.g., Windows, threads) this may fail
                    pass

            return self.session_id

    def end(self, reason: str = "exit") -> None:
        with self._lock:
            if self._ended or self.session_id is None:
                return
            duration = 0.0
            if self._start_monotonic is not None:
                duration = max(0.0, time.monotonic() - self._start_monotonic)

            end_record = SessionEndRecord(
                type="session_end",
                session_id=self.session_id,
                user_id=self.user_id,
                timestamp=self._utc_now_iso(),
                duration_seconds=duration,
                reason=reason,
            )
            self._append_jsonl(asdict(end_record))
            logger.info(
                "Session ended: id=%s duration=%.3fs reason=%s",
                self.session_id,
                duration,
                reason,
            )
            self._ended = True

    # Internal helpers -----------------------------------------------------

    def _atexit_end(self) -> None:
        try:
            self.end("atexit")
        except Exception:
            pass

    def _signal_handler(self, signum: int, frame: Any) -> None:  # noqa: ANN401
        # Write end record and then chain to default behaviour
        self.end("signal")
        # Re-raise the signal with default handler to preserve behaviour
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)


# Simple helpers for module-level usage ---------------------------------------
_global_tracker: Optional[SessionTracker] = None


def start_session(
    version: Optional[str] = None, context: Optional[Dict[str, Any]] = None
) -> SessionTracker:
    global _global_tracker
    # Start a new tracker if none exists or the previous one has ended
    if (
        _global_tracker is None
        or _global_tracker.session_id is None
        or getattr(_global_tracker, "_ended", False)
    ):
        _global_tracker = SessionTracker()
        _global_tracker.start(version=version, context=context)
    return _global_tracker


def end_session(reason: str = "exit") -> None:
    if _global_tracker is not None:
        _global_tracker.end(reason)
