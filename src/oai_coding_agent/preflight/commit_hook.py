"""
Git commit hook setup for OAI Coding Agent.
"""

import logging
from pathlib import Path

import git

from oai_coding_agent.xdg import get_data_dir

logger = logging.getLogger(__name__)

COMMIT_MSG_HOOK_SCRIPT = """#!/usr/bin/env sh
# commit-msg hook: append Co-Authored-By stanza when OAI_AGENT is set

if [ -n "$OAI_AGENT" ]; then
  printf "\\n🤖 Generated with OAI Coding Agent\\nCo-Authored-By: oai-coding-agent[bot] <214839426+oai-coding-agent[bot]@users.noreply.github.com>\\n" >> "$1"
fi
"""


def install_commit_msg_hook(repo_path: Path) -> None:
    """
    Install the commit-msg hook into the user's data dir so it's not tracked in the repo.
    """
    data_home = get_data_dir()
    hooks_dir = data_home / "hooks"
    hook_file = hooks_dir / "commit-msg"

    if not hooks_dir.exists():
        hooks_dir.mkdir(parents=True, exist_ok=True)

    existing = None
    if hook_file.exists():
        with open(hook_file, "r", encoding="utf-8") as f:
            existing = f.read()

    if existing != COMMIT_MSG_HOOK_SCRIPT:
        with open(hook_file, "w", encoding="utf-8") as f:
            f.write(COMMIT_MSG_HOOK_SCRIPT)
        hook_file.chmod(0o755)
        logger.info(f"Installed commit-msg hook into {hooks_dir}")

    try:
        repo = git.Repo(str(repo_path), search_parent_directories=True)
        repo.config_writer().set_value("core", "hooksPath", str(hooks_dir)).release()
        logger.info(f"Configured repo to use commit-msg hook from {hooks_dir}")
    except Exception as e:
        logger.warning(f"Failed to set git hooks path: {e}")
