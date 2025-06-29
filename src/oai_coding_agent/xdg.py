"""
XDG directory support
What is XDG? https://specifications.freedesktop.org/basedir-spec/latest/
"""

import os
from pathlib import Path


def get_config_dir() -> Path:
    """
    Return the OAI Coding Agent config directory under XDG_CONFIG_HOME or fallback to ~/.config.
    """
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "oai_coding_agent"


def get_data_dir() -> Path:
    """
    Return the OAI Coding Agent data directory under XDG_DATA_HOME or fallback to ~/.local/share.
    """
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return data_home / "oai_coding_agent"
