import webbrowser
from typing import Optional

import pyperclip
from prompt_toolkit import prompt
from rich import print
from rich.progress import Progress, SpinnerColumn, TextColumn

from oai_coding_agent.github.github_browser_auth import (
    poll_for_token,
    start_device_flow,
)
from oai_coding_agent.github.token_storage import (
    delete_github_token,
    get_github_token,
    save_github_token,
)


class GitHubConsole:
    def __init__(self) -> None:
        pass

    def _copy_to_clipboard(self, text: str) -> bool:
        """Try to copy text to clipboard. Returns True if successful."""
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            return False

    def authenticate(self) -> Optional[str]:
        """Core GitHub authentication flow."""
        print("\n[bold]Starting GitHub login...[/bold]")

        # Start device flow
        device_flow = start_device_flow()
        if not device_flow:
            print("[red]✗ Failed to start GitHub login[/red]")
            return None

        # Display the code
        print(
            f"\n[bold yellow]Your authentication code: {device_flow.user_code}[/bold yellow]"
        )

        # Try to copy to clipboard
        if self._copy_to_clipboard(device_flow.user_code):
            print("[dim]✓ Code copied to clipboard[/dim]")
        else:
            print("[dim]Copy this code - GitHub will ask for it[/dim]")

        # Prompt to open browser
        print(
            f"\nPress [bold]Enter[/bold] to open {device_flow.verification_uri} in your browser..."
        )
        input()

        # Open browser
        try:
            webbrowser.open(device_flow.verification_uri)
            print("[green]✓ Browser opened[/green]")
        except Exception:
            print(f"[yellow]Please visit: {device_flow.verification_uri}[/yellow]")

        print("\nNext steps:")
        print("  1. Log in to GitHub")
        print("  2. Enter the code shown above")
        print("  3. Authorize the application")

        # Poll for completion with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task("Waiting for authentication...", total=None)

            token = poll_for_token(
                device_flow.device_code,
                device_flow.interval,
                timeout=300,
            )

            progress.stop()

        if token:
            print("[green]✓ Successfully logged in to GitHub![/green]")
            save_github_token(token)

            return token
        else:
            print("[red]✗ Login failed or timed out[/red]")
            return None

    def prompt_auth(self) -> Optional[str]:
        """Prompt user to authenticate if no token is found."""
        token = get_github_token()
        if token:
            return token

        print("[yellow]GitHub integration not configured[/yellow]")
        print("Logging in to GitHub enables features like creating PRs and issues")
        print("Any actions taken will appear as if you did them directly")

        response = (
            prompt("\nWould you like to log in to GitHub? (y/n): ").strip().lower()
        )

        if response == "y":
            return self.authenticate()
        else:
            print("\n[dim]Continuing without GitHub integration[/dim]")
            print("You can log in later by running: [bold]oai github login[/bold]")
            return None

    def check_or_authenticate(self) -> Optional[str]:
        """Check for existing token or authenticate. Used by the auth subcommand."""
        token = get_github_token()
        if token:
            response = (
                prompt(
                    "You are already logged in to GitHub. Would you like to log in again? (y/n): "
                )
                .strip()
                .lower()
            )
            if response != "y":
                print("[green]Using existing GitHub login.[/green]")
                return token

        return self.authenticate()

    def logout(self) -> bool:
        """Log out from GitHub by removing stored token."""
        if not get_github_token():
            print("No stored GitHub token found.")
            return True

        response = (
            prompt("Are you sure you want to remove your GitHub token? (y/n): ")
            .strip()
            .lower()
        )

        if response == "y":
            if delete_github_token():
                print("[green]✓ Successfully logged out from GitHub.[/green]")
                print("You'll need to log in again to use GitHub features.")
                return True
            else:
                print("[red]✗ Failed to remove token.[/red]")
                return False
        else:
            print("Logout cancelled.")
            return True
