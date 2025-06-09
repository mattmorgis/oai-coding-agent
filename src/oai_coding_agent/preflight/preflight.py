"""
Preflight checks for the OAI Coding Agent CLI.
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import docker
from docker.errors import DockerException

from oai_coding_agent.preflight.commit_hook import install_commit_msg_hook
from oai_coding_agent.preflight.git_repo import (
    get_git_branch,
    get_github_repo,
    is_inside_git_repo,
)

logger = logging.getLogger(__name__)


class PreflightError(Exception):
    """Base exception for preflight check failures."""

    pass


class PreflightCheckError(PreflightError):
    """Raised when one or more preflight checks fail."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"Preflight checks failed: {'; '.join(errors)}")


def _get_tool_version(cmd: list[str]) -> str:
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


def _check_node() -> str:
    """
    Check that 'node' binary is on PATH and return its version string.
    """
    node_path = shutil.which("node")
    if not node_path:
        raise RuntimeError("Node.js binary not found on PATH")
    return _get_tool_version(["node", "--version"])


def _check_docker() -> str:
    """
    Check that Docker is available and return its version string.
    Uses the Docker Python SDK to verify daemon connectivity.
    """
    # First check if docker binary is on PATH for completeness
    docker_path = shutil.which("docker")
    if not docker_path:
        raise RuntimeError("Docker binary not found on PATH")

    # Use Docker SDK to verify daemon connectivity
    try:
        client = docker.from_env()
        # Ping the daemon to ensure it's running
        client.ping()
        # Get version info
        version_info = client.version()
        version_string = f"Docker version {version_info['Version']}"
        client.close()
        return version_string
    except DockerException as e:
        logger.error(f"Failed to connect to Docker daemon: {str(e)}")
        raise RuntimeError("Failed to connect to Docker daemon")
    except Exception as e:
        logger.error(f"Unexpected error checking Docker: {str(e)}")
        raise RuntimeError("Unexpected error checking Docker")


def run_preflight_checks(repo_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate preflight requirements:
      - Git worktree check
      - Node.js binary + version
      - Docker binary + version

    Raises:
        PreflightCheckError: If any preflight checks fail

    Returns:
        Tuple of (github_repo, branch_name) - both may be None if extraction fails
    """
    errors: list[str] = []

    if not is_inside_git_repo(repo_path):
        errors.append(f"Path '{repo_path}' is not inside a Git worktree.")

    node_version = ""
    try:
        node_version = _check_node()
    except RuntimeError as e:
        errors.append(str(e))

    docker_version = ""
    try:
        docker_version = _check_docker()
    except RuntimeError as e:
        errors.append(str(e))

    if errors:
        raise PreflightCheckError(errors)

    logger.info(f"Detected Node.js version: {node_version}")
    logger.info(f"Detected Docker version: {docker_version}")

    # Extract git info
    github_repo = get_github_repo(repo_path)
    branch_name = get_git_branch(repo_path)

    if github_repo:
        logger.info(f"Detected GitHub repository: {github_repo}")
    if branch_name:
        logger.info(f"Detected git branch: {branch_name}")

    # Auto-install the commit-msg hook into the user's config dir
    install_commit_msg_hook(repo_path)

    return github_repo, branch_name
