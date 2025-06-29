"""
Console subpackage: holds REPL loop, rendering, key bindings, slash-commands, and state.
"""

from oai_coding_agent.console.github_console import GitHubConsole
from oai_coding_agent.console.openai_console import OpenAIConsole

__all__ = ["GitHubConsole", "OpenAIConsole"]
