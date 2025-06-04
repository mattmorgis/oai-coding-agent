from pathlib import Path
from typing import Optional


def get_auth_file_path() -> Path:
    """Get the path to the OAI auth file in user's home directory."""
    return Path.home() / ".oai_coding_agent" / "auth"


def save_github_token(token: str) -> bool:
    """
    Save GitHub token to ~/.oai_coding_agent/auth file.

    Args:
        token: GitHub personal access token

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        auth_file = get_auth_file_path()

        # Create .oai_coding_agent directory if it doesn't exist
        auth_file.parent.mkdir(exist_ok=True)

        # Write token to auth file
        auth_file.write_text(f"GITHUB_TOKEN={token}\n")

        # Set secure permissions (read/write for user only)
        auth_file.chmod(0o600)

        return True
    except Exception:
        return False


def get_github_token() -> Optional[str]:
    """
    Retrieve GitHub token from ~/.oai_coding_agent/auth file.

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
    Delete the ~/.oai_coding_agent/auth file.

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
    Check if a GitHub token is stored in the auth file.

    Returns:
        True if token exists, False otherwise
    """
    return get_github_token() is not None
