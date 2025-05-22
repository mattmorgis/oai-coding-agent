import os
from enum import Enum
from pathlib import Path

import typer
from dotenv import dotenv_values
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from tui import ChatApp

console = Console()

# Only check for OPENAI_API_KEY in .env file without loading all variables
env_values = dotenv_values()
if "OPENAI_API_KEY" in env_values and env_values["OPENAI_API_KEY"] is not None:
    os.environ["OPENAI_API_KEY"] = str(env_values["OPENAI_API_KEY"])


class ModelChoice(str, Enum):
    o3 = "o3"
    o4_mini = "o4-mini"
    codex_mini_latest = "codex-mini-latest"


def config_table(model: ModelChoice, repo_path: Path) -> Table:
    table = Table()
    table.show_header = False
    table.show_lines = True
    table.add_row(
        "Model",
        model.value,
    )
    table.add_row("Repo Path", str(repo_path))

    return table


def main(
    openai_api_key: Annotated[str, typer.Argument(envvar="OPENAI_API_KEY")],
    model: Annotated[
        ModelChoice, typer.Option("--model", "-m", help="OpenAI model to use")
    ] = ModelChoice.o3,
    repo_path: Annotated[
        Path,
        typer.Option(
            help="Path to the repository. This path (and it's subdirectories) are the only files the agent has permission to access"
        ),
    ] = Path.cwd(),
):



if __name__ == "__main__":
    typer.run(main)
