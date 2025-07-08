import webbrowser
from pathlib import Path

from github import Github, GithubException
from github.Repository import Repository
from prompt_toolkit import PromptSession
from rich import print

from oai_coding_agent.runtime_config import RuntimeConfig

GITHUB_APP_SLUG = "oai-coding-agent"


class GitHubWorkflowConsole:
    def __init__(self, config: RuntimeConfig) -> None:
        self.prompt_session: PromptSession[str] = PromptSession(erase_when_done=True)
        self.config = config

    async def run(self) -> bool:
        """Run the complete GitHub workflow setup process."""
        if not await self.install_app():
            return False

        if not await self.setup_openai_secret():
            print("[bold red]Error:[/bold red] Failed to setup OpenAI API key secret")
            return False

        if not self.create_workflow_pr():
            print("[bold red]Error:[/bold red] Failed to create workflow PR")
            return False

        return True

    async def install_app(self) -> bool:
        """Prompt user to install GitHub App and wait for confirmation."""
        print("\n[bold]Install GitHub App[/bold]")
        print()
        print("To use GitHub workflows, you need to install the GitHub App.")
        print()

        try:
            print(
                "Press [bold]Enter[/bold] to open the GitHub App installation page in your browser",
            )
            await self.prompt_session.prompt_async()
        except (KeyboardInterrupt, EOFError):
            print("\n[dim]Installation cancelled[/dim]")
            return False

        # Open browser to app installation page
        app_url = f"https://github.com/apps/{GITHUB_APP_SLUG}/installations/new"
        try:
            webbrowser.open(app_url)
            print("[dim green]✓ Browser opened[/dim green]")
        except Exception:
            print(f"[dim]Please visit: {app_url}[/dim]")

        print()
        print("Next steps:")
        print("  1. Select the repositories you want to grant access to")
        print("  2. Click 'Install' to complete the installation")

        # Wait for user confirmation
        try:
            print("Press [bold]Enter[/bold] when you have completed the installation:")
            await self.prompt_session.prompt_async()
        except (KeyboardInterrupt, EOFError):
            print("\n[dim]Installation cancelled[/dim]")
            return False

        return True

    async def setup_openai_secret(self) -> bool:
        """Setup OpenAI API key as a repository secret."""
        print("\n[bold]Setup OpenAI API Key[/bold]")
        print()
        print("The workflow needs an OpenAI API key to function.")

        # Get API key from user
        api_key = await self._get_openai_api_key()
        if not api_key:
            return False

        # Setup the secret
        return self._create_repository_secret(api_key)

    async def _get_openai_api_key(self) -> str | None:
        """Prompt user for OpenAI API key choice."""
        current_key = self.config.openai_api_key

        if current_key:
            print(f"[dim]Current API key: {current_key[:8]}...{current_key[-4:]}[/dim]")
            print()
            print("Options:")
            print("  1. Use current API key")
            print("  2. Enter a different API key")
            print()

            try:
                choice = await self.prompt_session.prompt_async(
                    "Choose option (1 or 2): "
                )
                if choice.strip() == "1":
                    return current_key
                elif choice.strip() == "2":
                    return await self._prompt_for_new_api_key()
                else:
                    print("[bold red]Error:[/bold red] Invalid choice")
                    return None
            except (KeyboardInterrupt, EOFError):
                print("\n[dim]Setup cancelled[/dim]")
                return None
        else:
            print("No OpenAI API key found in current configuration.")
            return await self._prompt_for_new_api_key()

    async def _prompt_for_new_api_key(self) -> str | None:
        """Prompt user to enter a new API key."""
        try:
            print("Please enter your OpenAI API key:")
            api_key = await self.prompt_session.prompt_async(
                "API Key: ", is_password=True
            )
            api_key = api_key.strip()

            if not api_key:
                print("[bold red]Error:[/bold red] API key cannot be empty")
                return None

            if not api_key.startswith(("sk-", "sk-proj-")):
                print(
                    "[bold yellow]Warning:[/bold yellow] API key doesn't look like a standard OpenAI key"
                )
                print("[dim]Expected format: sk-... or sk-proj-...[/dim]")

                try:
                    confirm = await self.prompt_session.prompt_async(
                        "Continue anyway? (y/N): ", is_password=False
                    )
                    if confirm.lower() not in ("y", "yes"):
                        return None
                except (KeyboardInterrupt, EOFError):
                    return None

            return api_key

        except (KeyboardInterrupt, EOFError):
            print("\n[dim]Setup cancelled[/dim]")
            return None

    def _create_repository_secret(self, api_key: str) -> bool:
        """Create or update the OPENAI_API_KEY repository secret."""
        try:
            if not self.config.github_token:
                print("[bold red]Error:[/bold red] GitHub token not found")
                return False

            if not self.config.github_repo:
                print("[bold red]Error:[/bold red] GitHub repository not detected")
                return False

            g = Github(self.config.github_token)
            repo = g.get_repo(self.config.github_repo)

            secret_name = "OPENAI_API_KEY"

            try:
                # Try to update existing secret first
                repo.create_secret(secret_name, api_key)
                print(
                    f"[dim green]✓ Created repository secret '{secret_name}'[/dim green]"
                )
                return True
            except GithubException as e:
                if e.status == 422:  # Secret already exists
                    try:
                        # Update existing secret
                        repo.create_secret(secret_name, api_key)
                        print(
                            f"[dim green]✓ Updated repository secret '{secret_name}'[/dim green]"
                        )
                        return True
                    except Exception as update_error:
                        print(
                            f"[bold red]Error:[/bold red] Failed to update secret: {str(update_error)}"
                        )
                        return False
                else:
                    print(
                        f"[bold red]Error:[/bold red] Failed to create secret: {str(e)}"
                    )
                    return False

        except Exception as e:
            print(
                f"[bold red]Error:[/bold red] Failed to setup repository secret: {str(e)}"
            )
            return False

    def create_workflow_pr(self) -> bool:
        """Create a PR with the OAI agent workflow file"""
        print("\n[bold]Setting up OAI Agent Workflow[/bold]")

        try:
            if not self._check_prerequisites():
                return False

            workflow_content = self.load_workflow_template()
            if not workflow_content:
                return False

            repo = self._initialize_github_repo()
            if not repo:
                return False

            branch_name = self._create_or_update_branch(repo)
            if not branch_name:
                return False

            if not self._create_or_update_workflow_file(
                repo, workflow_content, branch_name
            ):
                return False

            return self._create_pull_request(repo, branch_name)

        except Exception as e:
            print(f"[bold red]Error:[/bold red] {str(e)}")
            return False

    def _check_prerequisites(self) -> bool:
        """Check if GitHub token and repo are available"""
        if not self.config.github_token:
            print(
                "[bold red]Error:[/bold red] GitHub token not found, must login with GitHub first"
            )
            return False

        if not self.config.github_repo:
            print("[bold red]Error:[/bold red] GitHub repository not detected")
            return False

        return True

    def _initialize_github_repo(self) -> Repository | None:
        """Initialize GitHub client and get repository"""
        try:
            g = Github(self.config.github_token)
            repo = g.get_repo(self.config.github_repo or "")
            return repo
        except Exception as e:
            print(f"[bold red]Error:[/bold red] Failed to access repository: {str(e)}")
            return None

    def _create_or_update_branch(self, repo: Repository) -> str | None:
        """Create or update the workflow branch"""
        try:
            main_branch = repo.get_branch(repo.default_branch)
            branch_name = "feature/add-oai-agent-workflow"

            try:
                repo.create_git_ref(f"refs/heads/{branch_name}", main_branch.commit.sha)
            except Exception:
                pass  # Branch already exists
            print(f"[dim green]✓ Created branch {branch_name}[/dim green]")
            return branch_name
        except Exception as e:
            print(f"[bold red]Error:[/bold red] Failed to create branch: {str(e)}")
            return None

    def _create_or_update_workflow_file(
        self, repo: Repository, workflow_content: str, branch_name: str
    ) -> bool:
        """Create or update the workflow file"""
        workflow_path = ".github/workflows/oai-agent.yml"

        try:
            repo.create_file(
                path=workflow_path,
                message="Add OAI Coding Agent workflow",
                content=workflow_content,
                branch=branch_name,
            )
            print("[dim green]✓ Created workflow file[/dim green]")
            return True
        except GithubException:
            # File might already exist, try to update it
            try:
                file = repo.get_contents(workflow_path, ref=branch_name)
                if isinstance(file, list):
                    file = file[0]

                repo.update_file(
                    path=workflow_path,
                    message="Update OAI Coding Agent workflow",
                    content=workflow_content,
                    sha=file.sha,
                    branch=branch_name,
                )
                print("[dim green]✓ Updated workflow file[/dim green]")
                return True
            except Exception as e:
                self._print_github_error("Failed to create/update workflow file", e)
                return False

    def _create_pull_request(self, repo: Repository, branch_name: str) -> bool:
        """Create the pull request"""
        try:
            pr = repo.create_pull(
                title="Add OAI Coding Agent GitHub Workflow",
                body="""This PR adds a GitHub workflow that automatically responds to:

    - An issue is labeled with `oai`
    - A comment on an issue or PR that contains `@oai`
    - A "changes requested" review on a PR authored by the agent

    The workflow will:
    1. Set up the required environment for the agent (Node.js, uv, oai-coding-agent)
    2. For issues: Create a new branch and PR with the solution
    3. For PR comments/reviews: Update the existing PR branch with requested changes
""",
                head=branch_name,
                base=repo.default_branch,
            )

            print("[bold green]✓ Successfully created pull request![/bold green]")
            print(f"[dim]PR URL: {pr.html_url}[/dim]")

            # Open PR in browser
            try:
                webbrowser.open(pr.html_url)
                print("[dim green]✓ Opened PR in browser[/dim green]")
            except Exception:
                pass  # Silently fail if browser can't be opened

            print()
            return True
        except GithubException as e:
            if e.status == 422 and "pull request already exists" in str(e).lower():
                print(
                    f"[bold yellow]Notice:[/bold yellow] A pull request already exists for branch '{branch_name}'"
                )
                print(
                    "[dim]You can update the existing PR or delete it to create a new one[/dim]"
                )
            else:
                self._print_github_error("Failed to create pull request", e)
            return False
        except Exception as e:
            self._print_github_error("Failed to create pull request", e)
            return False

    def _print_github_error(self, context: str, error: Exception) -> None:
        """Print a user-friendly GitHub error message"""
        if isinstance(error, GithubException):
            message = (
                error.data.get("message", str(error))
                if hasattr(error, "data") and error.data
                else str(error)
            )
            print(f"[bold red]Error:[/bold red] {context}: {message}")
        else:
            print(f"[bold red]Error:[/bold red] {context}: {str(error)}")

    def load_workflow_template(self) -> str | None:
        """Load the OAI agent workflow template"""
        template_path = Path(__file__).parent.parent / "templates" / "oai-agent.yaml"
        try:
            return template_path.read_text()
        except FileNotFoundError:
            print(
                f"[bold red]Error:[/bold red] Template file not found at {template_path}"
            )
            return None
