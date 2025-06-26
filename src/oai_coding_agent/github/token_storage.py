from pathlib import Path
from typing import Optional


def get_auth_file_path() -> Path:
    """Get the path to the OAI auth file in the XDG config directory."""
    from ..runtime_config import get_config_dir  # noqa: PLC0415

    return get_config_dir() / "auth"


def save_github_token(token: str) -> bool:
    """
    Save GitHub token to the auth file in the XDG config directory.

    Args:
        token: GitHub personal access token

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        auth_file = get_auth_file_path()

        # Create auth directory if it doesn't exist
        auth_file.parent.mkdir(parents=True, exist_ok=True)

        # Write token to auth file
        auth_file.write_text(f"GITHUB_TOKEN={token}\n")

        # Set secure permissions (read/write for user only)
        auth_file.chmod(0o600)

        return True
    except Exception:
        return False


def get_github_token() -> Optional[str]:
    """
    Retrieve GitHub token from the auth file in the XDG config directory.

    Returns:
        GitHub token if found, None otherwise
    """
    try:
        auth_file = get_auth_file_path()

        if not auth_file.exists():
            return None

        content = auth_file.read_text().strip()

        # Parse the GITHUB_TOKEN=value format
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                token = line.split("=", 1)[1]
                return token if token else None

        return None
    except Exception:
        return None


def delete_github_token() -> bool:
    """
    Delete the auth file in the XDG config directory.

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        auth_file = get_auth_file_path()
        if auth_file.exists():
            auth_file.unlink()
        return True
    except Exception:
        return False


def has_stored_token() -> bool:
    """
    Check if a GitHub token is stored in the auth file in the XDG config directory.

    Returns:
        True if token exists, False otherwise
    """
    return get_github_token() is not None
