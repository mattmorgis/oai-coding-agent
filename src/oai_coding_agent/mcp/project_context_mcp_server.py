#!/usr/bin/env python3
"""
Standalone MCP server for project context information.
This runs as a separate process and communicates via stdio.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from mcp import server
from mcp.types import TextContent, Tool

from .project_context import ProjectContext

app: Any = server.Server("project-context")


@app.list_tools()  # type: ignore[misc]
async def list_tools() -> List[Tool]:
    """List available project context tools."""
    return [
        Tool(
            name="get_project_structure",
            description="Get a rich directory tree with metadata for the project or a specific path",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (optional)",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth to traverse (default: 3)",
                        "default": 3,
                    },
                },
            },
        ),
        Tool(
            name="get_dependency_graph",
            description="Get import dependency graph starting from an entry point",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_point": {
                        "type": "string",
                        "description": "Path to the entry point file",
                    }
                },
                "required": ["entry_point"],
            },
        ),
        Tool(
            name="get_semantic_map",
            description="Get files grouped by functionality (AUTH, API, TEST, etc.)",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_file_metrics",
            description="Get detailed metrics for a specific file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"}
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="get_relevant_context",
            description="Get context relevant to a specific task or feature",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Description of the task or feature",
                    }
                },
                "required": ["task_description"],
            },
        ),
    ]


@app.call_tool()  # type: ignore[misc]
async def call_tool(
    name: str, arguments: Dict[str, Any] | None = None
) -> List[TextContent]:
    """Execute a tool and return results."""
    arguments = arguments or {}

    # Get repo path from environment or current directory
    repo_path = Path.cwd()
    context = ProjectContext(str(repo_path))

    try:
        if name == "get_project_structure":
            result = context.get_structure_summary(
                path=arguments.get("path"), max_depth=arguments.get("max_depth", 3)
            )
            return [TextContent(type="text", text=result)]

        elif name == "get_dependency_graph":
            dep_result = context.get_dependency_graph(arguments["entry_point"])
            formatted = _format_dependency_graph(dep_result)
            return [TextContent(type="text", text=formatted)]

        elif name == "get_semantic_map":
            sem_result = context.get_semantic_map()
            formatted = _format_semantic_map(sem_result)
            return [TextContent(type="text", text=formatted)]

        elif name == "get_file_metrics":
            metrics_result = context.get_file_metrics(arguments["path"])
            formatted = json.dumps(metrics_result, indent=2)
            return [TextContent(type="text", text=formatted)]

        elif name == "get_relevant_context":
            ctx_result = context.get_relevant_context(arguments["task_description"])
            formatted = _format_relevant_context(ctx_result)
            return [TextContent(type="text", text=formatted)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


def _format_dependency_graph(graph: Dict[str, List[str]]) -> str:
    """Format dependency graph for display."""
    lines = ["Dependency Graph:"]
    for file, deps in graph.items():
        if deps:
            lines.append(f"\n{file}:")
            for dep in deps:
                lines.append(f"  → {dep}")
    return "\n".join(lines)


def _format_semantic_map(semantic_map: Dict[str, List[str]]) -> str:
    """Format semantic map for display."""
    lines = ["Semantic Map:"]
    for tag, files in semantic_map.items():
        if files:
            lines.append(f"\n[{tag}] files:")
            for f in files[:5]:  # Show first 5
                lines.append(f"  - {f}")
            if len(files) > 5:
                lines.append(f"  ... and {len(files) - 5} more")
    return "\n".join(lines)


def _format_relevant_context(context: Dict[str, Any]) -> str:
    """Format relevant context for display."""
    lines = [f"Task: {' '.join(context['keywords'])}"]

    if context["relevant_files"]:
        lines.append("\nRelevant files:")
        for f in context["relevant_files"]:
            tags = f"{f['tags']}" if f["tags"] else ""
            lines.append(f"  - {f['path']} {tags}")

    if context["suggested_entry_points"]:
        lines.append("\nSuggested entry points:")
        for ep in context["suggested_entry_points"]:
            lines.append(f"  - {ep}")

    if context["related_modules"]:
        lines.append("\nRelated modules:")
        for mod in context["related_modules"]:
            lines.append(f"  - {mod}")

    return "\n".join(lines)


if __name__ == "__main__":
    import mcp.server.stdio

    async def main() -> None:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream, write_stream, app.create_initialization_options()
            )

    asyncio.run(main())
