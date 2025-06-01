import os
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import pytest

import oai_coding_agent.runtime_config as config_module
from oai_coding_agent.runtime_config import (
    ModeChoice,
    ModelChoice,
    RuntimeConfig,
    load_envs,
)


@pytest.mark.parametrize(
    "enum_class,expected_values",
    [
        (ModelChoice, {"codex-mini-latest", "o3", "o4-mini"}),
        (ModeChoice, {"default", "async", "plan"}),
    ],
)
def test_enum_values(enum_class: type[Enum], expected_values: set[str]) -> None:
    """Test that enum classes have the expected values."""
    choices = {c.value for c in enum_class}
    assert choices == expected_values


@pytest.mark.parametrize(
    "api_key,github_token,model,repo_path,mode,use_cwd",
    [
        # Test default repo_path (cwd) and default mode
        ("KEY", "TOK", ModelChoice.o3, None, None, True),
        # Test explicit repo_path and default mode
        ("A", "GH", ModelChoice.o4_mini, Path("/somewhere"), None, False),
        # Test explicit repo_path and custom mode
        ("A", "GH", ModelChoice.o4_mini, Path("/custom"), ModeChoice.plan, False),
    ],
)
def test_runtime_config_constructor(
    api_key: str,
    github_token: str,
    model: ModelChoice,
    repo_path: Optional[Path],
    mode: Optional[ModeChoice],
    use_cwd: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RuntimeConfig constructor with various parameter combinations."""
    expected_repo_path: Path
    if use_cwd:
        monkeypatch.chdir(tmp_path)
        expected_repo_path = tmp_path
    else:
        assert repo_path is not None  # Type narrowing for mypy
        expected_repo_path = repo_path

    kwargs: Dict[str, Any] = {
        "openai_api_key": api_key,
        "github_personal_access_token": github_token,
        "model": model,
    }
    if repo_path is not None:
        kwargs["repo_path"] = repo_path
    if mode is not None:
        kwargs["mode"] = mode

    cfg = RuntimeConfig(**kwargs)

    assert cfg.openai_api_key == api_key
    assert cfg.github_personal_access_token == github_token
    assert cfg.model == model
    assert cfg.repo_path == expected_repo_path
    assert cfg.mode == (mode or ModeChoice.default)


@pytest.fixture
def mock_dotenv(monkeypatch: pytest.MonkeyPatch) -> Callable[[Dict[str, str]], None]:
    """Mock dotenv_values to return test values."""

    def _mock(values: Dict[str, str]) -> None:
        monkeypatch.setattr(
            config_module, "dotenv_values", lambda env_file=None: values
        )

    return _mock


@pytest.mark.parametrize(
    "existing_env,dotenv_vals,expected",
    [
        # Test loading from dotenv when env vars not set
        (
            {},
            {"OPENAI_API_KEY": "FROM_ENV", "GITHUB_PERSONAL_ACCESS_TOKEN": "GH_ENV"},
            {"OPENAI_API_KEY": "FROM_ENV", "GITHUB_PERSONAL_ACCESS_TOKEN": "GH_ENV"},
        ),
        # Test not overriding existing env vars
        (
            {"OPENAI_API_KEY": "SHELL_KEY", "GITHUB_PERSONAL_ACCESS_TOKEN": "SHELL_GH"},
            {"OPENAI_API_KEY": "FROM_ENV", "GITHUB_PERSONAL_ACCESS_TOKEN": "GH_ENV"},
            {"OPENAI_API_KEY": "SHELL_KEY", "GITHUB_PERSONAL_ACCESS_TOKEN": "SHELL_GH"},
        ),
    ],
)
def test_load_envs_behavior(
    existing_env: Dict[str, str],
    dotenv_vals: Dict[str, str],
    expected: Dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    mock_dotenv: Callable[[Dict[str, str]], None],
) -> None:
    """Test load_envs behavior with different environment configurations."""
    # Clear env vars first
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)

    # Set existing env vars if any
    for key, value in existing_env.items():
        monkeypatch.setenv(key, value)

    # Mock dotenv values
    mock_dotenv(dotenv_vals)

    load_envs()

    assert os.environ.get("OPENAI_API_KEY") == expected["OPENAI_API_KEY"]
    assert (
        os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
        == expected["GITHUB_PERSONAL_ACCESS_TOKEN"]
    )


def test_load_envs_with_explicit_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ensure load_envs loads keys from an explicit .env file path
    env_file = tmp_path / ".custom_env"
    env_file.write_text(
        "OPENAI_API_KEY=EXPLICIT_KEY\nGITHUB_PERSONAL_ACCESS_TOKEN=EXPLICIT_GH\n"
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)

    load_envs(env_file=str(env_file))

    assert os.environ.get("OPENAI_API_KEY") == "EXPLICIT_KEY"
    assert os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") == "EXPLICIT_GH"
