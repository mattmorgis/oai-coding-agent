"""
Utility functions for OAI Coding Agent.
"""
import re

# Pattern to detect variations of "coding agent" or "code agent"
_CODING_AGENT_PATTERN = re.compile(r"\b(?:code|coding)[-\s]?agent\b", re.IGNORECASE)


def is_coding_task(text: str) -> bool:
    """
    Determine if the given text refers to a coding task assigned to the coding agent.

    Matches variations like "coding agent", "code agent", or "coding-agent" in a case-insensitive manner.

    Args:
        text: The text to evaluate.

    Returns:
        True if the text contains a coding agent assignee indication, False otherwise.
    """
    if not text:
        return False
    return bool(_CODING_AGENT_PATTERN.search(text))
