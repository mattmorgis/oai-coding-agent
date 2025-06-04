"""
Preflight checks for the OAI Coding Agent CLI.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import git
import typer
from jinja2 import Environment, PackageLoader, select_autoescape

from .git_repo import get_git_branch, get_github_repo, is_inside_git_repo

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Install commit-msg hook into user XDG_CONFIG_HOME so it's not tracked in the repo
# -----------------------------------------------------------------------------


def install_commit_msg_hook(repo_path: Path) -> None:
    """
    Install the commit-msg hook into the user's config dir so it's not tracked in the repo.
    """
    env = Environment(
        loader=PackageLoader("oai_coding_agent", "templates"),
        autoescape=select_autoescape([]),
    )
    template = env.get_template("commit_msg_hook.jinja2")
    hook_script = template.render()

    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    hooks_dir = config_home / "oai_coding_agent" / "hooks"
    hook_file = hooks_dir / "commit-msg"

    if not hooks_dir.exists():
        hooks_dir.mkdir(parents=True, exist_ok=True)

    existing = hook_file.read_text(encoding="utf-8") if hook_file.exists() else None
    if existing != hook_script:
        hook_file.write_text(hook_script, encoding="utf-8")
        hook_file.chmod(0o755)

    try:
        repo = git.Repo(repo_path, search_parent_directories=True)
        repo.config_writer().set_value("core", "hooksPath", str(hooks_dir)).release()
    except Exception as e:
        logger.warning(f"Failed to set git hooks path: {e}")


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

    # TODO: Switch to Docker SDK for Python for this check
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

    # Auto-install the commit-msg hook into the user's config dir
    install_commit_msg_hook(repo_path)

    return github_repo, branch_name
