"""
Preflight checks for the OAI Coding Agent CLI.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import typer

logger = logging.getLogger(__name__)


def is_inside_git_repo(repo_path: Path) -> bool:
    """
    Return True if the given path is inside a Git worktree.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise RuntimeError("Git binary not found on PATH")
    return result.returncode == 0 and result.stdout.strip() == "true"


def get_tool_version(cmd: list[str]) -> str:
    """
    Run the given command to get a tool's version string.
    Raises RuntimeError if command fails or is not found.
    """
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError(f"'{cmd[0]}' binary not found on PATH")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to run '{' '.join(cmd)}': {e}")


def check_node() -> str:
    """
    Check that 'node' binary is on PATH and return its version string.
    """
    node_path = shutil.which("node")
    if not node_path:
        raise RuntimeError("Node.js binary not found on PATH")
    return get_tool_version(["node", "--version"])


def check_docker() -> str:
    """
    Check that 'docker' binary is on PATH and return its version string.
    Additionally verifies that the Docker daemon is running.
    """
    docker_path = shutil.which("docker")
    if not docker_path:
        raise RuntimeError("Docker binary not found on PATH")

    # Verify that the Docker daemon is up and running
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        # (shouldn't really happen since we already did shutil.which)
        raise RuntimeError("'docker' binary not found on PATH")
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or "").strip() or str(e)
        raise RuntimeError(f"Failed to connect to Docker daemon: {msg}")

    # Now that the daemon is confirmed, grab & return the client version
    return get_tool_version(["docker", "--version"])


def get_github_repo(repo_path: Path) -> Optional[str]:
    """
    Extract GitHub repository in 'owner/repo' format from git remote.origin.url.
    Returns None if extraction fails.
    """
    try:
        raw = (
            subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=repo_path,
            )
            .decode()
            .strip()
        )
        # Remove trailing ".git"
        if raw.endswith(".git"):
            raw = raw[:-4]
        # SSH style: git@github.com:owner/repo
        if raw.startswith("git@"):
            _, path = raw.split(":", 1)
            return path
        # HTTPS style: https://github.com/owner/repo
        elif "://" in raw:
            return raw.split("://", 1)[1].split("/", 1)[1]
        else:
            return raw
    except Exception:
        return None


def get_git_branch(repo_path: Path) -> Optional[str]:
    """
    Get the current git branch name.
    Falls back to GITHUB_REF environment variable if direct extraction fails.
    Returns None if extraction fails.
    """
    try:
        branch_name = (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
            )
            .decode()
            .strip()
        )
        return branch_name
    except Exception:
        # Fallback to GITHUB_REF (useful in CI environments)
        ref = os.getenv("GITHUB_REF", "")
        if ref and "/" in ref:
            return ref.rsplit("/", 1)[-1]
        return None


def run_preflight_checks(repo_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate preflight requirements:
      - Git worktree check
      - Node.js binary + version
      - Docker binary + version
    On failure, prints errors and exits (typer.Exit).

    Returns:
        Tuple of (github_repo, branch_name) - both may be None if extraction fails
    """
    errors: list[str] = []

    if not is_inside_git_repo(repo_path):
        errors.append(f"Path '{repo_path}' is not inside a Git worktree.")

    node_version = ""
    try:
        node_version = check_node()
    except RuntimeError as e:
        errors.append(str(e))

    docker_version = ""
    try:
        docker_version = check_docker()
    except RuntimeError as e:
        errors.append(str(e))

    if errors:
        for err in errors:
            typer.echo(f"Error: {err}", err=True)
        raise typer.Exit(code=1)

    logger.info(f"Detected Node.js version: {node_version}")
    logger.info(f"Detected Docker version: {docker_version}")

    # Extract git info
    github_repo = get_github_repo(repo_path)
    branch_name = get_git_branch(repo_path)

    if github_repo:
        logger.info(f"Detected GitHub repository: {github_repo}")
    if branch_name:
        logger.info(f"Detected git branch: {branch_name}")

    return github_repo, branch_name
