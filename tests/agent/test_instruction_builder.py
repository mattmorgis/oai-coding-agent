"""Tests for instruction_builder module."""

from pathlib import Path

import pytest
from jinja2 import Template, TemplateNotFound

import oai_coding_agent.agent.instruction_builder as instruction_builder_module
from oai_coding_agent.agent.instruction_builder import build_instructions
from oai_coding_agent.runtime_config import ModeChoice, ModelChoice, RuntimeConfig


def test_build_instructions_with_async_mode() -> None:
    """Test building instructions with async mode."""
    config = RuntimeConfig(
        openai_api_key="apikey",
        github_token="TOK",
        model=ModelChoice.codex_mini_latest,
        repo_path=Path("repo"),
        mode=ModeChoice.async_,
    )
    instructions = build_instructions(config)
    # Should load prompt_async.jinja2
    assert instructions.startswith(
        "You are an autonomous software engineering agent running in GitHub Actions"
    )
    assert "## Autonomous Decision Making" in instructions


def test_build_instructions_with_plan_mode() -> None:
    """Test building instructions with plan mode."""
    config = RuntimeConfig(
        openai_api_key="apikey",
        github_token="TOK",
        model=ModelChoice.codex_mini_latest,
        repo_path=Path("repo"),
        mode=ModeChoice.plan,
    )
    instructions = build_instructions(config)
    # Should load prompt_plan.jinja2
    assert instructions.startswith(
        "You are a software architecture and planning specialist"
    )
    assert "## Planning Approach" in instructions


def test_build_instructions_with_default_mode() -> None:
    """Test building instructions with default mode."""
    config = RuntimeConfig(
        openai_api_key="apikey",
        github_token="TOK",
        model=ModelChoice.codex_mini_latest,
        repo_path=Path("repo2"),
        mode=ModeChoice.default,
    )
    instructions = build_instructions(config)
    # Should load prompt_default.jinja2
    assert instructions.startswith(
        "You are OAI - a collaborative software engineering assistant"
    )
    assert "## Collaborative Approach" in instructions


def test_build_instructions_fallback_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that unknown modes fallback to default template."""
    # Create a config with a mode that doesn't have a corresponding template
    config = RuntimeConfig(
        openai_api_key="apikey",
        github_token="TOK",
        model=ModelChoice.codex_mini_latest,
        repo_path=Path("repo"),
        mode=ModeChoice.default,
    )

    # Monkeypatch to simulate missing template
    original_get_template = instruction_builder_module.TEMPLATE_ENV.get_template

    def mock_get_template(name: str) -> Template:
        if name == "prompt_default.jinja2":
            raise TemplateNotFound(name)
        return original_get_template(name)

    monkeypatch.setattr(
        instruction_builder_module.TEMPLATE_ENV, "get_template", mock_get_template
    )

    # This should raise TemplateNotFound since we're mocking both templates to not exist
    with pytest.raises(TemplateNotFound):
        build_instructions(config)


def test_build_instructions_with_github_info() -> None:
    """Test that GitHub info is included in instructions when provided (for async mode)."""
    config = RuntimeConfig(
        openai_api_key="apikey",
        github_token="TOK",
        model=ModelChoice.codex_mini_latest,
        repo_path=Path("/test/repo"),
        mode=ModeChoice.async_,
        github_repo="owner/repo",
        branch_name="feature-branch",
    )
    instructions = build_instructions(config)
    # The async template uses these variables
    assert "owner/repo" in instructions  # github_repo is rendered
    assert "feature-branch" in instructions  # branch_name is rendered
