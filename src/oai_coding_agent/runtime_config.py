"""
Runtime configuration for the OAI coding agent.

This module provides:
- load_envs(): load OPENAI_API_KEY, GITHUB_TOKEN, and OPENAI_BASE_URL from a .env file
  if they are not already present in the environment.
- RuntimeConfig: a dataclass holding runtime settings, including API keys, base URL,
  model choice, repo path, and mode.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

from oai_coding_agent.auth.token_storage import get_auth_file_path

# Environment variable names for credentials and endpoints
OPENAI_API_KEY_ENV: str = "OPENAI_API_KEY"
OPENAI_BASE_URL_ENV: str = "OPENAI_BASE_URL"
GITHUB_TOKEN: str = "GITHUB_TOKEN"


def load_envs(env_file: Optional[str] = None) -> None:
    """
    Load OPENAI_API_KEY, GITHUB_TOKEN, and OPENAI_BASE_URL from .env files
    into the process environment if they are not already set.

    Loads from:
    1. Auth file in the XDG data directory (for GITHUB_TOKEN)
    2. .env file (project-specific settings)
    3. Specified env_file (if provided)
    """
    # Load from multiple sources in order of precedence
    sources = []

    # 1. Load from auth file in the XDG data directory first (for GITHUB_TOKEN)

    auth_file = get_auth_file_path()
    if auth_file.exists():
        sources.append(str(auth_file))

    # 2. Load from .env file in current directory
    if not env_file:
        sources.append(".env")
    else:
        # 3. Load from specified env file
        sources.append(env_file)

    # Load environment variables from all sources
    for source in sources:
        try:
            env_values = dotenv_values(source)
            for key in (OPENAI_API_KEY_ENV, GITHUB_TOKEN, OPENAI_BASE_URL_ENV):
                if not os.environ.get(key):
                    val = env_values.get(key)
                    if val:
                        os.environ[key] = str(val)
        except Exception:
            # Silently ignore missing or unreadable files
            continue


class ModelChoice(str, Enum):
    """Supported OpenAI model choices."""

    codex_mini_latest = "codex-mini-latest"
    o3 = "o3"
    o3_pro = "o3-pro"
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
        openai_base_url: Custom base URL for the OpenAI API endpoint (if provided).
        github_token: The GitHub Token to use for the GitHub MCP server.
        model: The OpenAI model identifier.
        repo_path: Path to the repository to work on.
        mode: The agent mode to use.
        github_repo: The GitHub repository in "owner/repo" format (if available).
        branch_name: The current git branch name (if available).
        prompt: The prompt text for headless mode (if provided).
        atlassian: Enable Atlassian MCP server (only works in plan mode).
    """

    openai_api_key: str
    github_token: Optional[str]
    model: ModelChoice
    repo_path: Path = field(default_factory=Path.cwd)
    mode: ModeChoice = ModeChoice.default
    openai_base_url: Optional[str] = None
    github_repo: Optional[str] = None
    branch_name: Optional[str] = None
    prompt: Optional[str] = None
    atlassian: bool = False
