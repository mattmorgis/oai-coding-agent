import time
import webbrowser
from typing import Optional

import requests

from oai_coding_agent.auth.token_storage import get_auth_file_path, save_github_token

# Using GitHub CLI's client ID for device flow
# This is a public client ID the GitHub Coding Agent application
GITHUB_APP_CLIENT_ID = "Ov23liCVY3S4HY5FMODo"


def authenticate_github_browser() -> Optional[str]:
    """
    Authenticate with GitHub using browser-based flow.

    This uses GitHub's Device Flow which allows users to authenticate
    with their GitHub credentials in a browser, similar to how Claude Code
    authenticates with Claude AI.

    The user logs in with their own GitHub account, and GitHub determines
    access based on their permissions to repositories and organizations.

    Requests full repository access (repo scope) which includes:
    - Code access (read/write repository files)
    - Pull requests (create, read, update PRs)
    - Issues (create, read, update issues)
    - Repository metadata and settings

    Returns:
        GitHub personal access token or None if authentication fails
    """

    # Request full repository access
    scopes = [
        "repo",  # Full access to repositories (public and private)
        "read:user",  # Read basic user profile information
    ]

    print("Requesting full access to your GitHub repositories")
    print("Permissions include: code, pull requests, issues, and repository metadata")

    device_response = requests.post(
        "https://github.com/login/device/code",
        data={"client_id": GITHUB_APP_CLIENT_ID, "scope": " ".join(scopes)},
        headers={"Accept": "application/json"},
    )

    if device_response.status_code != 200:
        print("\n✗ Failed to initiate GitHub authentication")
        return None

    device_data = device_response.json()
    device_code = device_data["device_code"]
    user_code = device_data["user_code"]
    verification_uri = device_data["verification_uri"]
    interval = device_data.get("interval", 5)

    # Display authentication instructions
    print("\n🔐 Opening browser for GitHub authentication...")
    print("\n┌─────────────────────────────────┐")
    print("│  Your authentication code:      │")
    print("│                                 │")
    print(f"│         {user_code}               │")
    print("│                                 │")
    print("│  (Copy this - GitHub will ask)  │")
    print("└─────────────────────────────────┘")

    # Open browser
    try:
        webbrowser.open(verification_uri)
        print(f"\n✓ Browser opened to: {verification_uri}")
        print("  → Log in to GitHub")
        print("  → Enter the code shown above when prompted")
        print("  → Authorize the application")
    except Exception:
        print(f"\n🌐 Please visit: {verification_uri}")
        print("  → Log in to GitHub")
        print("  → Enter the code shown above when prompted")
        print("  → Authorize the application")

    print("\nWaiting for authentication...")

    # Poll for authentication completion
    start_time = time.time()
    dots = 0

    while time.time() - start_time < 300:  # 5 minute timeout
        time.sleep(interval)

        # Show progress dots
        dots = (dots + 1) % 4
        print(f"\r{'.' * dots}{' ' * (3 - dots)}", end="", flush=True)

        # Check if user has completed authentication
        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_APP_CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json"},
        )

        if token_response.status_code == 200:
            result = token_response.json()

            if "access_token" in result:
                # Clear the progress dots
                print("\r   \r", end="", flush=True)
                print("✓ Successfully authenticated with GitHub!")
                access_token = result["access_token"]
                if isinstance(access_token, str):
                    # Automatically save token to auth file in XDG data directory
                    if save_github_token(access_token):
                        print(
                            f"✓ Token saved to {get_auth_file_path()} for future sessions"
                        )
                    else:
                        print(
                            "⚠️  Could not save token (will need to re-authenticate next time)"
                        )
                    return access_token

            elif result.get("error") == "authorization_pending":
                # User hasn't completed auth yet, continue waiting
                continue

            elif result.get("error") == "slow_down":
                # We're polling too fast, increase interval
                interval = result.get("interval", interval + 5)

            else:
                # Some other error occurred
                print("\r   \r", end="", flush=True)
                error_msg = result.get(
                    "error_description", result.get("error", "Unknown error")
                )
                print(f"\n✗ Authentication failed: {error_msg}")
                return None

    # Timeout reached
    print("\r   \r", end="", flush=True)
    print("\n✗ Authentication timeout - please try again")
    return None
