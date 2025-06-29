import json
from typing import Any, Dict, Protocol

from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Heading, Markdown
from rich.syntax import Syntax
from rich.text import Text
from rich.tree import Tree

from oai_coding_agent.agent.events import (
    AgentEvent,
    ErrorEvent,
    MessageOutputEvent,
    ReasoningEvent,
    ToolCallEvent,
    ToolCallOutputEvent,
)


# Classes to override the default Markdown renderer
class PlainHeading(Heading):
    """Left-aligned, no panel."""

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        self.text.justify = "left"
        yield self.text


class PlainMarkdown(Markdown):
    elements = Markdown.elements.copy()
    elements["heading_open"] = PlainHeading


# Apply override globally for Markdown
Markdown.elements["heading_open"] = PlainHeading


console = Console()


class EventRenderer(Protocol):
    """Protocol for event-specific renderers."""

    def render(self, event: AgentEvent) -> None:
        """Render the event to console."""
        ...


class ToolCallManager:
    """Manages pairing of tool calls with their outputs."""

    def __init__(self) -> None:
        self.pending_tool_calls: Dict[str, ToolCallEvent] = {}

    def handle_tool_call(self, tool_call: ToolCallEvent) -> None:
        """Store tool call for later pairing with output."""
        if tool_call.call_id:
            self.pending_tool_calls[tool_call.call_id] = tool_call
        else:
            # Render immediately if no call_id (can't be paired)
            render_tool_call_standalone(tool_call)

    def handle_tool_output(self, tool_output: ToolCallOutputEvent) -> bool:
        """Handle tool output and render paired tool call if found."""
        if tool_output.call_id in self.pending_tool_calls:
            tool_call = self.pending_tool_calls.pop(tool_output.call_id)
            render_tool_call_with_output(tool_call, tool_output)
            return True
        return False


def _parse_output_data(output: str) -> str:
    """Parse and extract text from tool output."""
    try:
        output_data = json.loads(output)
        if isinstance(output_data, dict) and "text" in output_data:
            return str(output_data["text"])
        elif isinstance(output_data, list):
            # Handle run_command output format: [{'type': 'text', 'text': '...'}]
            text_parts = []
            for item in output_data:
                if (
                    isinstance(item, dict)
                    and item.get("type") == "text"
                    and "text" in item
                ):
                    text_parts.append(item["text"])
            return "".join(text_parts)
        else:
            return output
    except json.JSONDecodeError:
        return output


def _truncate_output_lines(text: str, max_lines: int = 8) -> str:
    """Truncate multi-line text to at most max_lines, appending ellipsis if needed."""
    lines = text.split("\n")
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + "\n..."
    return text


def render_tool_call_standalone(tool_call: ToolCallEvent) -> None:
    """Render a tool call without output."""
    title = Text(f"{tool_call.name}", style="green bold")
    console.print(title)

    if tool_call.arguments:
        try:
            args_data = json.loads(tool_call.arguments)
            if isinstance(args_data, dict):
                for key, value in args_data.items():
                    console.print(f"  [dim]{key}:[/dim] {value}")
            else:
                console.print(f"  [dim]args:[/dim] {tool_call.arguments}")
        except json.JSONDecodeError:
            console.print(f"  [dim]args:[/dim] {tool_call.arguments}")

    console.print()


def render_tool_call_with_output(
    tool_call: ToolCallEvent, tool_output: ToolCallOutputEvent
) -> None:
    """Render a tool call with its output using tool-specific formatting."""
    output_text = _parse_output_data(tool_output.output)

    # Parse arguments for tool-specific rendering
    try:
        args_data = json.loads(tool_call.arguments)
    except json.JSONDecodeError:
        args_data = {}

    # Dispatch to tool-specific renderers
    if tool_call.name == "read_file":
        render_read_file_tool(tool_call, output_text, args_data)
    elif tool_call.name == "edit_file":
        render_edit_file_tool(tool_call, output_text, args_data)
    elif tool_call.name == "list_directory":
        render_list_directory_tool(tool_call, output_text, args_data)
    elif tool_call.name == "search_files":
        render_search_files_tool(tool_call, output_text, args_data)
    elif tool_call.name == "read_multiple_files":
        render_read_multiple_files_tool(tool_call, output_text, args_data)
    elif tool_call.name == "directory_tree":
        render_directory_tree_tool(tool_call, output_text, args_data)
    elif tool_call.name == "write_file":
        render_write_file_tool(tool_call, output_text, args_data)
    elif tool_call.name == "move_file":
        render_move_file_tool(tool_call, output_text, args_data)
    elif tool_call.name == "git_add":
        render_git_add_tool(tool_call, output_text, args_data)
    elif tool_call.name == "git_commit":
        render_git_commit_tool(tool_call, output_text, args_data)
    elif tool_call.name == "git_status":
        render_git_status_tool(tool_call, output_text, args_data)
    elif tool_call.name in ["run_command", "shell"]:
        render_command_tool(tool_call, output_text, args_data)

    else:
        render_generic_tool(tool_call, output_text, args_data)


def render_read_file_tool(
    tool_call: ToolCallEvent, output_text: str, args_data: Dict[str, Any]
) -> None:
    """Render read_file tool as a tree with line count."""
    filename = args_data.get("path", "file")

    lines = output_text.split("\n")
    line_count = len([line for line in lines if line.strip()])

    root = Tree(Text("▶ Reading ") + Text(filename, style="bold"))
    root.add(Text(f"{line_count} line{'s' if line_count != 1 else ''}", style="green"))
    console.print(root)
    console.print()


def render_edit_file_tool(
    tool_call: ToolCallEvent, output_text: str, args_data: Dict[str, Any]
) -> None:
    """Render edit_file tool as a tree with diff output."""
    filename = args_data.get("path", "file")

    # Determine label color based on presence of error/failure keywords
    lower_out = output_text.lower()
    label_style = "red" if ("error" in lower_out or "failed" in lower_out) else ""
    label = Text("▶ Edited ", style=label_style) + Text(filename, style="bold")
    root = Tree(label)
    if output_text.strip():
        diff_syntax = Syntax(output_text, "diff", theme="ansi_dark", line_numbers=False)
        root.add(diff_syntax)
    console.print(root)
    console.print()


def render_list_directory_tool(
    tool_call: ToolCallEvent, tool_output: str, args_data: Dict[str, Any]
) -> None:
    """Render list_directory tool with directory contents."""
    directory_name = args_data.get("path", ".")

    lines = [line.strip() for line in tool_output.strip().split("\n") if line.strip()]

    file_count = sum(1 for line in lines if line.startswith("[FILE]"))
    dir_count = sum(1 for line in lines if line.startswith("[DIR]"))
    total = file_count + dir_count

    root = Tree(
        Text("▶ Listing directory: ") + Text(f"{directory_name}/", style="bold")
    )

    if total == 0:
        root.add(Text("empty", style="green"))
    else:
        parts = []
        if file_count > 0:
            parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")
        if dir_count > 0:
            parts.append(f"{dir_count} director{'ies' if dir_count != 1 else 'y'}")
        root.add(Text(f"{total} items: {', '.join(parts)}", style="green"))

    console.print(root)
    console.print()


def render_search_files_tool(
    tool_call: ToolCallEvent, tool_output: str, args_data: Dict[str, Any]
) -> None:
    """Render search_files tool as a tree with the result count."""
    path = args_data.get("path", ".")
    pattern = args_data.get("pattern", "")
    lines = [line.strip() for line in tool_output.strip().split("\n") if line.strip()]
    result_count = len(lines)

    root = Tree(
        Text("▶ Searched ")
        + Text(f'"{pattern}"', style="bold")
        + Text(" in ")
        + Text(f"{path}/", style="bold")
    )
    style = "green" if result_count > 0 else "red"
    root.add(
        Text(f"{result_count} result{'s' if result_count != 1 else ''}", style=style)
    )
    console.print(root)
    console.print()


def render_read_multiple_files_tool(
    tool_call: ToolCallEvent, tool_output: str, args_data: Dict[str, Any]
) -> None:
    """Render read_multiple_files tool as a tree listing the files read."""
    paths = args_data.get("paths", [])
    root = Tree(Text("▶ Read multiple files:"))
    for path in paths:
        root.add(Text(path, style="bold"))
    console.print(root)
    console.print()


def render_directory_tree_tool(
    tool_call: ToolCallEvent, tool_output: str, args_data: Dict[str, Any]
) -> None:
    """Render a simple one-line summary for directory_tree tool."""
    path = args_data.get("path", ".")
    header = Text("▶ Listed directory tree for ") + Text(f"{path}/", style="bold")
    console.print(header)
    console.print()


def render_write_file_tool(
    tool_call: ToolCallEvent, tool_output: str, args_data: Dict[str, Any]
) -> None:
    """Render write_file tool as a tree with line count."""
    path = args_data.get("path", "")
    content = args_data.get("content", "") or ""
    lines = [line for line in content.split("\n") if line.strip()]
    count = len(lines)

    root = Tree(Text("▶ Wrote ") + Text(path, style="bold"))
    root.add(Text(f"{count} line{'s' if count != 1 else ''} written", style="green"))
    console.print(root)
    console.print()


def render_move_file_tool(
    tool_call: ToolCallEvent, tool_output: str, args_data: Dict[str, Any]
) -> None:
    """Render move_file tool with source→destination and status."""
    src = args_data.get("source", "")
    dest = args_data.get("destination", "")
    root = Tree(
        Text("▶ Moving: ")
        + Text(src, style="bold")
        + Text(" → ")
        + Text(dest, style="bold")
    )
    style = "green" if "success" in tool_output.lower() else "red"
    root.add(Text(_truncate_output_lines(tool_output), style=style))
    console.print(root)
    console.print()


def render_git_add_tool(
    tool_call: ToolCallEvent, tool_output: str, args_data: Dict[str, Any]
) -> None:
    """Render git_add tool with a rich tree for staging files."""
    files = args_data.get("files", [])
    # Root tree node showing staging files list
    root = Tree(Text("▶ Staging files: ") + Text(", ".join(files), style="bold"))
    # Add output as child node, color green for success, red otherwise
    style = "green" if "success" in tool_output.lower() else "red"
    root.add(Text(_truncate_output_lines(tool_output), style=style))
    console.print(root)
    console.print()


def render_git_commit_tool(
    tool_call: ToolCallEvent, tool_output: str, args_data: Dict[str, Any]
) -> None:
    """Render git_commit tool with a rich tree for commit message and output."""
    message = args_data.get("message", "")
    root = Tree(Text("▶ Committing with message: \n") + Text(message, style="bold"))
    style = "red" if "failed" in tool_output.lower() else "green"
    root.add(Text(_truncate_output_lines(tool_output), style=style))
    console.print(root)
    console.print()


def render_git_status_tool(
    tool_call: ToolCallEvent, output_text: str, args_data: Dict[str, Any]
) -> None:
    """Render git_status tool with a tree showing status output."""
    root = Tree(Text("▶ Running git_status", style="bold"))
    if output_text.strip():
        root.add(Text(output_text, style="dim"))
    console.print(root)
    console.print()


def render_command_tool(
    tool_call: ToolCallEvent, output_text: str, args_data: Dict[str, Any]
) -> None:
    """Render shell/command tool with command and output."""
    command = (
        tool_call.arguments
        if tool_call.name == "shell"
        else args_data.get("command", "")
    )

    # Render command as tree header
    root_label = Text("▶ Running command: ") + Text(command, style="bold")
    root = Tree(root_label)

    if output_text.strip():
        # Truncate output for readability
        truncated = _truncate_output_lines(output_text)
        lower_out = truncated.lower()
        err_style = "red" if ("error" in lower_out or "failed" in lower_out) else "dim"
        root.add(Text(truncated, style=err_style))

    console.print(root)
    console.print()


def render_generic_tool(
    tool_call: ToolCallEvent, output_text: str, args_data: Dict[str, Any]
) -> None:
    """Render generic tool calls."""
    # Build argument list for display
    args_list = []
    if isinstance(args_data, dict):
        for key, value in args_data.items():
            args_list.append(f"{key}={value}")
    elif tool_call.arguments:
        args_list.append(tool_call.arguments)

    args_str = " ".join(args_list)
    # Create tree header
    root_label = Text("▶ Calling ") + Text(tool_call.name, style="bold")
    if args_str:
        root_label.append(" with ")
        root_label.append(args_str, style="bold")
    root = Tree(root_label)

    if output_text.strip():
        truncated = _truncate_output_lines(output_text)
        root.add(Text(truncated, style="dim"))

    console.print(root)
    console.print()


# Global tool call manager
_tool_manager = ToolCallManager()


def render_event(event: AgentEvent) -> None:
    """Render an agent event with rich formatting."""
    match event:
        case ToolCallEvent() as tool_call:
            _tool_manager.handle_tool_call(tool_call)

        case ToolCallOutputEvent() as tool_output:
            # Try to pair with tool call, if not found render standalone
            if not _tool_manager.handle_tool_output(tool_output):
                output_text = _parse_output_data(tool_output.output)
                if len(output_text) > 200:
                    output_text = output_text[:200] + "..."
                console.print(
                    f"[dim]unpaired tool output:[/dim] [dim green]{output_text}[/dim green]"
                )
                console.print()

        case ReasoningEvent(text=text):
            md = Markdown(
                text, code_theme="ansi_dark", hyperlinks=True, style="dim italic"
            )
            console.print(md)
            console.print()

        case MessageOutputEvent(text=text):
            md = Markdown(text, code_theme="ansi_dark", hyperlinks=True)
            console.print(md)
            console.print()

        case ErrorEvent(message=msg):
            header = Text("Error", style="bold red")
            console.print(header)
            console.print(f"  {msg}")
            console.print()
