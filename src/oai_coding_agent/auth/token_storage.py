import os
from pathlib import Path
from typing import Optional


def get_auth_file_path() -> Path:
    """Get the path to the OAI auth file in user's home directory."""
    return Path.home() / ".oai" / "auth"


def save_github_token(token: str) -> bool:
    """
    Save GitHub token to ~/.oai/auth file.
    
    Args:
        token: GitHub personal access token
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        auth_file = get_auth_file_path()
        
        # Create .oai directory if it doesn't exist
        auth_file.parent.mkdir(exist_ok=True)
        
        # Write token to auth file
        auth_file.write_text(f"GITHUB_PERSONAL_ACCESS_TOKEN={token}\n")
        
        # Set secure permissions (read/write for user only)
        auth_file.chmod(0o600)
        
        return True
    except Exception:
        return False


def get_github_token() -> Optional[str]:
    """
    Retrieve GitHub token from ~/.oai/auth file.
    
    Returns:
        GitHub token if found, None otherwise
    """
    try:
        auth_file = get_auth_file_path()
        
        if not auth_file.exists():
            return None
            
        content = auth_file.read_text().strip()
        
        # Parse the GITHUB_PERSONAL_ACCESS_TOKEN=value format
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('GITHUB_PERSONAL_ACCESS_TOKEN='):
                token = line.split('=', 1)[1]
                return token if token else None
                
        return None
    except Exception:
        return None


def delete_github_token() -> bool:
    """
    Delete the ~/.oai/auth file.
    
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


def load_auth_to_environment() -> None:
    """
    Load authentication from ~/.oai/auth file into environment variables.
    Only sets variables that are not already set in the environment.
    """
    try:
        auth_file = get_auth_file_path()
        
        if not auth_file.exists():
            return
            
        content = auth_file.read_text().strip()
        
        # Parse each line and set environment variables
        for line in content.split('\n'):
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Only set if not already in environment
                if key and value and not os.environ.get(key):
                    os.environ[key] = value
                    
    except Exception:
        # Silently ignore errors when loading auth file
        pass