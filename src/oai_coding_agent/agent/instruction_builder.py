"""
Build dynamic instructions from templates.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from oai_coding_agent.runtime_config import RuntimeConfig

TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent.parent / "templates"),
    autoescape=False,
    keep_trailing_newline=True,
)


def build_instructions(config: RuntimeConfig) -> str:
    """Build instructions from template based on configuration."""
    try:
        template = TEMPLATE_ENV.get_template(f"prompt_{config.mode.value}.jinja2")
    except TemplateNotFound:
        template = TEMPLATE_ENV.get_template("prompt_default.jinja2")

    return template.render(
        repo_path=str(config.repo_path),
        mode=config.mode.value,
        github_repository=config.github_repo or "",
        branch_name=config.branch_name or "",
    )
