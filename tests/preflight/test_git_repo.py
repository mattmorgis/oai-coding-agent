"""Test the git module using GitPython."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import git
import pytest

from oai_coding_agent.preflight.git_repo import (
    get_git_branch,
    get_github_repo,
    is_inside_git_repo,
)


def test_is_inside_git_repo_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test when path is inside a valid git repo."""
    mock_repo = MagicMock()
    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)

    assert is_inside_git_repo(Path("/some/repo")) is True


def test_is_inside_git_repo_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test when path is not inside a git repo."""

    def raise_invalid(*args: Any, **kwargs: Any) -> None:
        raise git.InvalidGitRepositoryError()

    monkeypatch.setattr(git, "Repo", raise_invalid)

    assert is_inside_git_repo(Path("/not/a/repo")) is False


def test_is_inside_git_repo_no_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test when path doesn't exist."""

    def raise_no_path(*args: Any, **kwargs: Any) -> None:
        raise git.NoSuchPathError()

    monkeypatch.setattr(git, "Repo", raise_no_path)

    assert is_inside_git_repo(Path("/nonexistent")) is False


def test_get_github_repo_https(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test extracting GitHub repo from HTTPS URL."""
    mock_repo = MagicMock()
    mock_origin = MagicMock()
    mock_origin.url = "https://github.com/owner/repo.git"
    mock_remotes = MagicMock()
    mock_remotes.__contains__ = lambda self, key: key == "origin"
    mock_remotes.origin = mock_origin
    mock_repo.remotes = mock_remotes

    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)

    assert get_github_repo(Path("/some/repo")) == "owner/repo"


def test_get_github_repo_ssh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test extracting GitHub repo from SSH URL."""
    mock_repo = MagicMock()
    mock_origin = MagicMock()
    mock_origin.url = "git@github.com:owner/repo.git"
    mock_remotes = MagicMock()
    mock_remotes.__contains__ = lambda self, key: key == "origin"
    mock_remotes.origin = mock_origin
    mock_repo.remotes = mock_remotes

    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)

    assert get_github_repo(Path("/some/repo")) == "owner/repo"


def test_get_github_repo_non_github_https(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that non-GitHub HTTPS remotes return None."""
    mock_repo = MagicMock()
    mock_origin = MagicMock()
    mock_origin.url = "https://gitlab.com/owner/repo.git"
    mock_remotes = MagicMock()
    mock_remotes.__contains__ = lambda self, key: key == "origin"
    mock_remotes.origin = mock_origin
    mock_repo.remotes = mock_remotes

    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)

    assert get_github_repo(Path("/some/repo")) is None


def test_get_github_repo_non_github_ssh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that non-GitHub SSH remotes return None."""
    mock_repo = MagicMock()
    mock_origin = MagicMock()
    mock_origin.url = "git@bitbucket.org:owner/repo.git"
    mock_remotes = MagicMock()
    mock_remotes.__contains__ = lambda self, key: key == "origin"
    mock_remotes.origin = mock_origin
    mock_repo.remotes = mock_remotes

    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)

    assert get_github_repo(Path("/some/repo")) is None


def test_get_github_repo_no_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test when repo has no origin remote."""
    mock_repo = MagicMock()
    mock_remotes = MagicMock()
    mock_remotes.__contains__ = lambda self, key: False
    mock_repo.remotes = mock_remotes

    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)

    assert get_github_repo(Path("/some/repo")) is None


def test_get_git_branch_normal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test getting current branch name."""
    mock_repo = MagicMock()
    mock_branch = MagicMock()
    mock_branch.name = "main"
    mock_repo.active_branch = mock_branch
    mock_repo.head.is_detached = False

    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)

    assert get_git_branch(Path("/some/repo")) == "main"


def test_get_git_branch_detached_with_github_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test getting branch from GITHUB_REF when in detached HEAD state."""
    mock_repo = MagicMock()
    mock_repo.head.is_detached = True

    monkeypatch.setattr(git, "Repo", lambda *args, **kwargs: mock_repo)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/feature/branch")

    # The function now returns the full branch path after refs/heads/, e.g. 'feature/branch'
    assert get_git_branch(Path("/some/repo")) == "feature/branch"


def test_get_git_branch_error_with_github_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fallback to GITHUB_REF when GitPython fails."""

    # When GITHUB_REF has full path, we still return everything after 'refs/heads/'

    def raise_error(*args: Any, **kwargs: Any) -> None:
        raise Exception("Git error")

    monkeypatch.setattr(git, "Repo", raise_error)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/fallback")

    assert get_git_branch(Path("/some/repo")) == "fallback"
