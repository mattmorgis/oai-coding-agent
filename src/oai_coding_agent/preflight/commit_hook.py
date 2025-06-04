"""
Git commit hook setup for OAI Coding Agent.
"""

import logging
import os
from pathlib import Path

import git
from jinja2 import Environment, PackageLoader, select_autoescape

logger = logging.getLogger(__name__)


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
