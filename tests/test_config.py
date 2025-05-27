import os
import sys
import importlib
from pathlib import Path
import pytest

import oai_coding_agent.config as config_module
from oai_coding_agent.config import ModelChoice, Config


def test_model_choice_enum_values():
    # Ensure ModelChoice enum has expected values
    choices = {c.value for c in ModelChoice}
    assert {"codex-mini-latest", "o3", "o4-mini"} == choices


def test_config_init_defaults_repo_path(tmp_path, monkeypatch):
    # Default repo_path should be current working directory
    monkeypatch.chdir(tmp_path)
    cfg = Config(
        openai_api_key="KEY",
        github_personal_access_token="TOK",
        model=ModelChoice.o3,
    )
    assert cfg.openai_api_key == "KEY"
    assert cfg.github_personal_access_token == "TOK"
    assert cfg.model == ModelChoice.o3
    assert cfg.repo_path == tmp_path


def test_config_from_cli_sets_attributes():
    rp = Path("/somewhere")
    cfg = Config.from_cli(
        openai_api_key="A",
        github_personal_access_token="GH",
        model=ModelChoice.o4_mini,
        repo_path=rp,
    )
    assert isinstance(cfg, Config)
    assert cfg.openai_api_key == "A"
    assert cfg.github_personal_access_token == "GH"
    assert cfg.model == ModelChoice.o4_mini
    assert cfg.repo_path == rp


def test_dotenv_load_sets_env(monkeypatch):
    # Ensure that config module uses dotenv_values to set OPENAI_API_KEY
    import sys, types

    # Prepare fake dotenv module
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.dotenv_values = lambda: {"OPENAI_API_KEY": "FROM_ENV"}
    # Patch sys.modules to inject fake dotenv
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    # Remove and reload config_module to apply fake dotenv
    monkeypatch.setenv("OPENAI_API_KEY", "", prepend=False)
    sys.modules.pop("oai_coding_agent.config", None)
    new_config = importlib.import_module("oai_coding_agent.config")

    try:
        assert os.environ.get("OPENAI_API_KEY") == "FROM_ENV"
    finally:
        # Cleanup: restore real config module and dotenv
        sys.modules["oai_coding_agent.config"] = config_module
        importlib.reload(config_module)
        # Remove fake dotenv
        if sys.modules.get("dotenv") is fake_dotenv:
            sys.modules.pop("dotenv")


def test_dotenv_load_sets_github_token(monkeypatch):
    # Ensure that config module uses dotenv_values to set GITHUB_PERSONAL_ACCESS_TOKEN
    import sys, types

    # Prepare fake dotenv module
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.dotenv_values = lambda: {"GITHUB_PERSONAL_ACCESS_TOKEN": "GH_ENV"}
    # Patch sys.modules to inject fake dotenv
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    # Remove and reload config_module to apply fake dotenv
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
    sys.modules.pop("oai_coding_agent.config", None)
    new_config = importlib.import_module("oai_coding_agent.config")

    try:
        assert os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") == "GH_ENV"
    finally:
        # Cleanup: restore real config module and dotenv
        sys.modules["oai_coding_agent.config"] = config_module
        importlib.reload(config_module)
        # Remove fake dotenv
        if sys.modules.get("dotenv") is fake_dotenv:
            sys.modules.pop("dotenv")


# Clean up import cache to prevent side effects
@pytest.fixture(autouse=True)
def reload_config_module():
    """
    Reload the config module after each test to restore original state.
    """
    yield
    import sys

    # Ensure original config_module is registered in sys.modules
    if "oai_coding_agent.config" not in sys.modules:
        sys.modules["oai_coding_agent.config"] = config_module
    importlib.reload(config_module)
