"""
Configuration module for the OAI coding agent.

This module auto-loads environment variables from a .env file
and provides a Config data class for collecting runtime settings.
"""

import os
from pathlib import Path
from enum import Enum
from typing import Optional

from dotenv import dotenv_values

# Load OPENAI_API_KEY from .env if present
_env = dotenv_values()
_key = _env.get("OPENAI_API_KEY")
if _key:
    os.environ["OPENAI_API_KEY"] = str(_key)

# Load GITHUB_PERSONAL_ACCESS_TOKEN from .env if present
_github_key = _env.get("GITHUB_PERSONAL_ACCESS_TOKEN")
if _github_key:
    os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = str(_github_key)


class ModelChoice(str, Enum):
    """Supported OpenAI model choices."""

    codex_mini_latest = "codex-mini-latest"
    o3 = "o3"
    o4_mini = "o4-mini"


class ModeChoice(str, Enum):
    """Supported agent mode choices."""

    default = "default"
    async_ = "async"
    plan = "plan"


class Config:
    """
    Holds runtime configuration for the OAI coding agent.

    Attributes:
        openai_api_key: The OpenAI API key to use.
        github_personal_access_token: The GitHub Personal Access Token to use for the GitHub MCP server.
        model: The OpenAI model identifier.
        repo_path: Path to the repository to work on.
        mode: The agent mode to use.
        (Additional fields can be added as needed.)
    """

    def __init__(
        self,
        openai_api_key: str,
        github_personal_access_token: str,
        model: ModelChoice,
        repo_path: Optional[Path] = None,
        mode: ModeChoice = ModeChoice.default,
    ):
        self.openai_api_key = openai_api_key
        self.github_personal_access_token = github_personal_access_token
        self.model = model
        self.repo_path = repo_path or Path.cwd()
        self.mode = mode

    @classmethod
    def from_cli(
        cls,
        openai_api_key: str,
        github_personal_access_token: str,
        model: ModelChoice,
        repo_path: Optional[Path] = None,
        mode: ModeChoice = ModeChoice.default,
    ) -> "Config":
        """
        Build a Config object from CLI-supplied parameters.
        """
        return cls(
            openai_api_key=openai_api_key,
            github_personal_access_token=github_personal_access_token,
            model=model,
            repo_path=repo_path,
            mode=mode,
        )
