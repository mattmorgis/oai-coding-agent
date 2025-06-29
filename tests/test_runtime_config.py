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
from oai_coding_agent.xdg import get_config_dir, get_data_dir


@pytest.mark.parametrize(
    "enum_class,expected_values",
    [
        (ModelChoice, {"codex-mini-latest", "o3", "o4-mini", "o3-pro"}),
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
        "github_token": github_token,
        "model": model,
    }
    if repo_path is not None:
        kwargs["repo_path"] = repo_path
    if mode is not None:
        kwargs["mode"] = mode

    cfg = RuntimeConfig(**kwargs)

    assert cfg.openai_api_key == api_key
    assert cfg.github_token == github_token
    assert cfg.model == model
    assert cfg.repo_path == expected_repo_path
    assert cfg.mode == (mode or ModeChoice.default)
    assert cfg.openai_base_url is None
    assert cfg.atlassian is False  # default value


def test_runtime_config_constructor_with_base_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that RuntimeConfig accepts an explicit openai_base_url."""
    monkeypatch.chdir(tmp_path)
    custom_url = "https://custom.openai"
    cfg = RuntimeConfig(
        openai_api_key="KEY",
        openai_base_url=custom_url,
        github_token="GH",
        model=ModelChoice.o3,
    )
    assert cfg.openai_base_url == custom_url
    assert cfg.repo_path == tmp_path
    assert cfg.mode == ModeChoice.default
    assert cfg.atlassian is False  # default value


def test_runtime_config_constructor_with_atlassian_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that RuntimeConfig accepts an explicit atlassian flag."""
    monkeypatch.chdir(tmp_path)
    cfg = RuntimeConfig(
        openai_api_key="KEY",
        github_token="GH",
        model=ModelChoice.o3,
        mode=ModeChoice.plan,
        atlassian=True,
    )
    assert cfg.atlassian is True
    assert cfg.mode == ModeChoice.plan


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
            {"OPENAI_API_KEY": "FROM_ENV", "GITHUB_TOKEN": "GH_ENV"},
            {"OPENAI_API_KEY": "FROM_ENV", "GITHUB_TOKEN": "GH_ENV"},
        ),
        # Test not overriding existing env vars
        (
            {"OPENAI_API_KEY": "SHELL_KEY", "GITHUB_TOKEN": "SHELL_GH"},
            {"OPENAI_API_KEY": "FROM_ENV", "GITHUB_TOKEN": "GH_ENV"},
            {"OPENAI_API_KEY": "SHELL_KEY", "GITHUB_TOKEN": "SHELL_GH"},
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
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    # Set existing env vars if any
    for key, value in existing_env.items():
        monkeypatch.setenv(key, value)

    # Mock dotenv values
    mock_dotenv(dotenv_vals)

    load_envs()

    assert os.environ.get("OPENAI_API_KEY") == expected["OPENAI_API_KEY"]
    assert os.environ.get("GITHUB_TOKEN") == expected["GITHUB_TOKEN"]


@pytest.mark.parametrize(
    "existing_env,dotenv_vals,expected_url",
    [
        # Test loading base URL when not set
        ({}, {"OPENAI_BASE_URL": "FROM_ENV"}, "FROM_ENV"),
        # Test not overriding existing base URL
        (
            {"OPENAI_BASE_URL": "SHELL_URL"},
            {"OPENAI_BASE_URL": "FROM_ENV"},
            "SHELL_URL",
        ),
    ],
)
def test_load_envs_openai_base_url(
    existing_env: Dict[str, str],
    dotenv_vals: Dict[str, str],
    expected_url: str,
    monkeypatch: pytest.MonkeyPatch,
    mock_dotenv: Callable[[Dict[str, str]], None],
) -> None:
    """Test that load_envs loads or preserves OPENAI_BASE_URL correctly."""
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    for key, value in existing_env.items():
        monkeypatch.setenv(key, value)
    mock_dotenv(dotenv_vals)

    load_envs()

    assert os.environ.get("OPENAI_BASE_URL") == expected_url


def test_load_envs_with_explicit_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ensure load_envs loads keys from an explicit .env file path
    env_file = tmp_path / ".custom_env"
    env_file.write_text(
        "OPENAI_API_KEY=EXPLICIT_KEY\nGITHUB_TOKEN=EXPLICIT_GH\nOPENAI_BASE_URL=EXPLICIT_URL\n"
    )

    # Clear environment variables first
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    # Mock get_auth_file_path to return a non-existent file to avoid loading auth file
    monkeypatch.setattr(
        "oai_coding_agent.runtime_config.get_auth_file_path",
        lambda: Path("/nonexistent/auth/file"),
    )

    load_envs(env_file=str(env_file))

    assert os.environ.get("OPENAI_API_KEY") == "EXPLICIT_KEY"
    assert os.environ.get("GITHUB_TOKEN") == "EXPLICIT_GH"
    assert os.environ.get("OPENAI_BASE_URL") == "EXPLICIT_URL"


@pytest.mark.parametrize(
    "home_dir",
    [Path("/fake/home")],
)
def test_get_dirs_default(monkeypatch: pytest.MonkeyPatch, home_dir: Path) -> None:
    """Test get_data_dir and get_config_dir default fallbacks when XDG vars not set."""
    # Ensure no XDG env vars
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    # Set HOME to a known location
    monkeypatch.setenv("HOME", str(home_dir))

    expected_data = home_dir / ".local" / "share" / "oai_coding_agent"
    expected_config = home_dir / ".config" / "oai_coding_agent"

    assert get_data_dir() == expected_data
    assert get_config_dir() == expected_config


def test_get_data_dir_with_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test get_data_dir uses XDG_DATA_HOME when set."""
    xdg_data = tmp_path / "xdg_data"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))
    # Set HOME so fallback isn't accidentally used
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    expected_data = xdg_data / "oai_coding_agent"
    assert get_data_dir() == expected_data


def test_get_config_dir_with_xdg(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test get_config_dir uses XDG_CONFIG_HOME when set."""
    xdg_config = tmp_path / "xdg_config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    # Set HOME so fallback isn't accidentally used
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    expected_config = xdg_config / "oai_coding_agent"
    assert get_config_dir() == expected_config
