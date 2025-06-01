import os
from pathlib import Path

import pytest

import oai_coding_agent.runtime_config as config_module
from oai_coding_agent.runtime_config import (
    ModeChoice,
    ModelChoice,
    RuntimeConfig,
    load_envs,
)


def test_model_choice_enum_values() -> None:
    choices = {c.value for c in ModelChoice}
    assert {"codex-mini-latest", "o3", "o4-mini"} == choices


def test_mode_choice_enum_values() -> None:
    choices = {c.value for c in ModeChoice}
    assert {"default", "async", "plan"} == choices


def test_runtime_config_init_defaults_repo_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Default repo_path should be current working directory and default mode
    monkeypatch.chdir(tmp_path)
    cfg = RuntimeConfig(
        openai_api_key="KEY",
        github_personal_access_token="TOK",
        model=ModelChoice.o3,
    )
    assert cfg.openai_api_key == "KEY"
    assert cfg.github_personal_access_token == "TOK"
    assert cfg.model == ModelChoice.o3
    assert cfg.repo_path == tmp_path
    assert cfg.mode == ModeChoice.default


def test_runtime_config_constructor_sets_attributes() -> None:
    rp = Path("/somewhere")
    cfg = RuntimeConfig(
        openai_api_key="A",
        github_personal_access_token="GH",
        model=ModelChoice.o4_mini,
        repo_path=rp,
    )
    assert isinstance(cfg, RuntimeConfig)
    assert cfg.openai_api_key == "A"
    assert cfg.github_personal_access_token == "GH"
    assert cfg.model == ModelChoice.o4_mini
    assert cfg.repo_path == rp
    assert cfg.mode == ModeChoice.default


def test_runtime_config_constructor_with_custom_mode() -> None:
    rp = Path("/custom")
    cfg = RuntimeConfig(
        openai_api_key="A",
        github_personal_access_token="GH",
        model=ModelChoice.o4_mini,
        repo_path=rp,
        mode=ModeChoice.plan,
    )
    assert cfg.mode == ModeChoice.plan


def test_load_envs_sets_openai_and_github_if_not_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ensure load_envs loads keys from dotenv when not in env
    # Fake dotenv_values so load_envs picks up our values.
    vals = {"OPENAI_API_KEY": "FROM_ENV", "GITHUB_PERSONAL_ACCESS_TOKEN": "GH_ENV"}
    monkeypatch.setattr(config_module, "dotenv_values", lambda env_file=None: vals)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)

    load_envs()

    assert os.environ.get("OPENAI_API_KEY") == "FROM_ENV"
    assert os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") == "GH_ENV"


def test_load_envs_does_not_override_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure load_envs does not override existing env vars
    # Fake dotenv_values so load_envs picks up our values.
    vals = {"OPENAI_API_KEY": "FROM_ENV", "GITHUB_PERSONAL_ACCESS_TOKEN": "GH_ENV"}
    monkeypatch.setattr(config_module, "dotenv_values", lambda env_file=None: vals)

    monkeypatch.setenv("OPENAI_API_KEY", "SHELL_KEY")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "SHELL_GH")

    load_envs()

    assert os.environ.get("OPENAI_API_KEY") == "SHELL_KEY"
    assert os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") == "SHELL_GH"


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
