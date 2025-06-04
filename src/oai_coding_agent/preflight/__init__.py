"""
Preflight checks for the OAI Coding Agent CLI.
"""

from .commit_hook import install_commit_msg_hook
from .preflight import PreflightCheckError, PreflightError, run_preflight_checks

__all__ = [
    "run_preflight_checks",
    "install_commit_msg_hook",
    "PreflightError",
    "PreflightCheckError",
]
