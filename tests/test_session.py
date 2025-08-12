from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from oai_coding_agent.session import (
    generate_session_id,
    get_basic_stats,
    get_sessions_log_path,
    record_session,
)


@pytest.fixture(autouse=True)
def isolate_xdg_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # prevent writing to real XDG_DATA_HOME during tests
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg_data"))


def test_generate_session_id_is_uuid4() -> None:
    sid = generate_session_id()
    parsed = UUID(sid)
    assert parsed.version == 4


def test_record_session_appends_and_stats(tmp_path: Path) -> None:
    # Write two session records with known timestamps
    ts1 = "2025-01-01T00:00:00+00:00"
    ts2 = "2025-01-02T00:00:00+00:00"

    sid1 = record_session(repo_path=tmp_path, now_ts=ts1)
    sid2 = record_session(repo_path=tmp_path, now_ts=ts2)

    assert sid1 != sid2
    # Validate UUID format
    assert UUID(sid1).version == 4
    assert UUID(sid2).version == 4

    log_path = get_sessions_log_path()
    assert log_path.exists()

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    rec1 = json.loads(lines[0])
    rec2 = json.loads(lines[1])

    assert rec1["timestamp"] == ts1
    assert rec2["timestamp"] == ts2
    assert rec1["repo_path"] == str(tmp_path)

    total, last_ts = get_basic_stats()
    assert total == 2
    assert last_ts == ts2
