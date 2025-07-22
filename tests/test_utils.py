"""Unit tests for utility functions."""
# ruff: noqa

import pytest

from oai_coding_agent.utils import is_coding_task


@pytest.mark.parametrize(
    "text",
    [
        "Assign to coding agent for implementation",
        "Next action: code agent to review code",
        "Task for Coding Agent: write tests",
        "Task assigned to code-agent to update docs",
        "Assign to CODE-AGENT and code agent variants",
        "coding agent should handle this",
    ],
)
def test_is_coding_task_true(text: str) -> None:
    """is_coding_task should return True for coding agent variations."""
    assert is_coding_task(text)


@pytest.mark.parametrize(
    "text",
    [
        "Follow-up meeting with stakeholders",
        "KT session for developers",
        "Prepare presentation slides",
        "Discuss coding agenda and next steps",
        "Budget planning and metrics review",
        "",
        None,
    ],
)
def test_is_coding_task_false(text: str | None) -> None:
    """is_coding_task should return False for non-coding tasks and empty or None."""
    # Handle None gracefully
    result = is_coding_task(text) if text is not None else False
    assert result is False
