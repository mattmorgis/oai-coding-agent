from pathlib import Path
from typing import Dict, Optional

from ..xdg import get_config_dir

_AUTH_FILE = "auth"


def get_auth_file_path() -> Path:
    """Dotenv-style auth file under XDG_CONFIG_HOME/oai_coding_agent."""
    return get_config_dir() / _AUTH_FILE


def _read_entries() -> Dict[str, str]:
    """Load all KEY=VALUE lines from the auth file (silently returns {} if missing)."""
    auth_file = get_auth_file_path()
    try:
        lines = auth_file.read_text().splitlines()
    except FileNotFoundError:
        return {}
    entries: Dict[str, str] = {}
    for line in lines:
        if "=" in line:
            k, v = line.split("=", 1)
            entries[k] = v
    return entries


def _write_entries(entries: Dict[str, str]) -> bool:
    """Overwrite the auth file with the given KEY=VALUE entries (secure perms)."""
    auth_file = get_auth_file_path()
    try:
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(f"{k}={v}" for k, v in entries.items()) + "\n"
        auth_file.write_text(content)
        auth_file.chmod(0o600)
        return True
    except Exception:
        return False


def save_token(key: str, token: str) -> bool:
    """Set or update a token in the auth file under the given KEY."""
    entries = _read_entries()
    entries[key] = token
    return _write_entries(entries)


def get_token(key: str) -> Optional[str]:
    """Retrieve the token value for KEY from the auth file (or None)."""
    return _read_entries().get(key)


def delete_token(key: str) -> bool:
    """Remove KEY (and its token) from the auth file."""
    entries = _read_entries()
    entries.pop(key, None)
    return _write_entries(entries)


def has_token(key: str) -> bool:
    """True if KEY exists in the auth file."""
    return get_token(key) is not None
