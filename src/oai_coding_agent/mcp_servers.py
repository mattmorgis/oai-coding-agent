"""
Launch and register cleanup for filesystem, CLI & Git MCP servers via AsyncExitStack.
"""
import logging
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import List

from agents.mcp import MCPServerStdio
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

# CLI MCP server restrictions
ALLOWED_CLI_COMMANDS = [
    "grep",
    "rg",
    "find",
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "pwd",
    "echo",
    "sed",
    "awk",
    "sort",
    "uniq",
    "fzf",
    "bat",
    "git",
    "uv",
    "pip",
    "pipdeptree",
    "xargs",
    "which",
]

ALLOWED_CLI_FLAGS = ["all"]


class QuietMCPServerStdio(MCPServerStdio):
    """Variant of MCPServerStdio that silences child-process stderr."""

    def create_streams(self):
        return stdio_client(self.params, errlog=open(os.devnull, "w"))


async def start_mcp_servers(repo_path: Path, exit_stack: AsyncExitStack) -> List[MCPServerStdio]:
    """
    Start filesystem, CLI, and Git MCP servers, registering cleanup on the provided exit_stack.

    Returns a list of connected MCPServerStdio instances.
    """
    servers: List[MCPServerStdio] = []

    # Filesystem MCP server
    fs_ctx = QuietMCPServerStdio(
        name="file-system-mcp",
        params={
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(repo_path),
            ],
        },
        client_session_timeout_seconds=30,
        cache_tools_list=True,
    )
    fs = await fs_ctx.__aenter__()
    exit_stack.push_async_callback(fs_ctx.__aexit__, None, None, None)
    servers.append(fs)

    # CLI MCP server
    try:
        cli_ctx = QuietMCPServerStdio(
            name="cli-mcp-server",
            params={
                "command": "cli-mcp-server",
                "env": {
                    "ALLOWED_DIR": str(repo_path),
                    "ALLOWED_COMMANDS": ",".join(ALLOWED_CLI_COMMANDS),
                    "ALLOWED_FLAGS": ",".join(ALLOWED_CLI_FLAGS),
                    "ALLOW_SHELL_OPERATORS": "true",
                    "COMMAND_TIMEOUT": "120",
                },
            },
            client_session_timeout_seconds=120,
            cache_tools_list=True,
        )
        cli = await cli_ctx.__aenter__()
        exit_stack.push_async_callback(cli_ctx.__aexit__, None, None, None)
        servers.append(cli)
        logger.info("CLI MCP server started successfully")
    except OSError:
        logger.exception("Failed to start CLI MCP server")

    # Git MCP server
    try:
        git_ctx = QuietMCPServerStdio(
            name="mcp-server-git",
            params={
                "command": "mcp-server-git",
            },
            client_session_timeout_seconds=120,
            cache_tools_list=True,
        )
        git = await git_ctx.__aenter__()
        exit_stack.push_async_callback(git_ctx.__aexit__, None, None, None)
        servers.append(git)
        logger.info("Git MCP server started successfully")
    except OSError:
        logger.exception("Failed to start Git MCP server")

    return servers
