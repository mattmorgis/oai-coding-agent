"""
Git-related utilities for preflight checks.
"""

import logging
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import git

logger = logging.getLogger(__name__)


def is_inside_git_repo(repo_path: Path) -> bool:
    """
    Return True if the given path is inside a Git worktree.
    """
    try:
        git.Repo(repo_path, search_parent_directories=True)
        return True
    except git.InvalidGitRepositoryError:
        return False
    except git.NoSuchPathError:
        return False


def get_github_repo(repo_path: Path) -> Optional[str]:
    """
    Extract GitHub repository in 'owner/repo' format from git remote.origin.url.
    Returns None if extraction fails.
    """
    try:
        repo = git.Repo(repo_path, search_parent_directories=True)
        if "origin" not in repo.remotes:
            return None

        origin_url = repo.remotes.origin.url

        # Remove trailing ".git"
        if origin_url.endswith(".git"):
            origin_url = origin_url[:-4]

        # SSH style: git@github.com:owner/repo
        if origin_url.startswith("git@"):
            _, path = origin_url.split(":", 1)
            return path

        # HTTPS style: https://github.com/owner/repo
        parsed = urlparse(origin_url)
        if parsed.scheme and parsed.netloc:
            # Remove leading slash from path
            return parsed.path.lstrip("/")

        return origin_url
    except Exception as e:
        logger.debug(f"Failed to extract GitHub repo: {e}")
        return None


def get_git_branch(repo_path: Path) -> Optional[str]:
    """
    Get the current git branch name.
    Falls back to GITHUB_REF environment variable if direct extraction fails.
    Returns None if extraction fails.
    """
    try:
        repo = git.Repo(repo_path, search_parent_directories=True)
        if repo.head.is_detached:
            # In detached HEAD state, try to get branch from GITHUB_REF
            ref = os.getenv("GITHUB_REF", "")
            if ref and "/" in ref:
                return ref.rsplit("/", 1)[-1]
            return None
        return repo.active_branch.name
    except Exception as e:
        logger.debug(f"Failed to get git branch: {e}")
        # Fallback to GITHUB_REF (useful in CI environments)
        ref = os.getenv("GITHUB_REF", "")
        if ref and "/" in ref:
            return ref.rsplit("/", 1)[-1]
        return None
