"""
Runtime configuration for the OAI coding agent.

This module provides:
- load_envs(): load OPENAI_API_KEY and GITHUB_PERSONAL_ACCESS_TOKEN from a .env file
  if they are not already present in the environment.
- RuntimeConfig: a dataclass holding runtime settings, including API keys,
  model choice, repo path, and mode.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

# Environment variable names for credentials
OPENAI_API_KEY_ENV: str = "OPENAI_API_KEY"
GITHUB_PERSONAL_ACCESS_TOKEN_ENV: str = "GITHUB_PERSONAL_ACCESS_TOKEN"


def load_envs(env_file: Optional[str] = None) -> None:
    """
    Load OPENAI_API_KEY and GITHUB_PERSONAL_ACCESS_TOKEN from a .env file
    into the process environment if they are not already set.
    """
    env_values = dotenv_values(env_file) if env_file else dotenv_values()
    for key in (OPENAI_API_KEY_ENV, GITHUB_PERSONAL_ACCESS_TOKEN_ENV):
        if not os.environ.get(key):
            val = env_values.get(key)
            if val:
                os.environ[key] = str(val)


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


@dataclass(frozen=True)
class RuntimeConfig:
    """
    Holds runtime configuration for the OAI coding agent.

    Attributes:
        openai_api_key: The OpenAI API key to use.
        github_personal_access_token: The GitHub Personal Access Token to use for the GitHub MCP server.
        model: The OpenAI model identifier.
        repo_path: Path to the repository to work on.
        mode: The agent mode to use.
        github_repo: The GitHub repository in "owner/repo" format (if available).
        branch_name: The current git branch name (if available).
        prompt: The prompt text for headless mode (if provided).
    """

    openai_api_key: str
    github_personal_access_token: str
    model: ModelChoice
    repo_path: Path = field(default_factory=Path.cwd)
    mode: ModeChoice = ModeChoice.default
    github_repo: Optional[str] = None
    branch_name: Optional[str] = None
    prompt: Optional[str] = None
