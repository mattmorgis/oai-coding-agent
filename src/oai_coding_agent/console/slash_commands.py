from oai_coding_agent.console.rendering import clear_terminal, render_message
from oai_coding_agent.console.state import UIMessage, UIState


def register_slash_commands(state: UIState) -> None:
    """Register all available slash commands on the given state."""
    state.slash_commands.clear()

    def cmd_help(args: str = "") -> bool:
        """Show help information for available commands."""
        help_text = "Available Commands:\n\n"
        for cmd, func in state.slash_commands.items():
            doc = func.__doc__ or "No description available"
            help_text += f"/{cmd} - {doc}\n"
        msg: UIMessage = {"role": "system", "content": help_text}
        render_message(msg)
        return True

    def cmd_clear(args: str = "") -> bool:
        """Clear the terminal screen."""
        clear_terminal()
        msg: UIMessage = {"role": "system", "content": "Terminal has been cleared."}
        render_message(msg)
        return True

    def cmd_exit(args: str = "") -> bool:
        """Exit the application."""
        return False

    def cmd_version(args: str = "") -> bool:
        """Show version information."""
        msg: UIMessage = {
            "role": "system",
            "content": "CLI Chat Version: 0.1.0\nBuilt with Rich and prompt-toolkit",
        }
        render_message(msg)
        return True

    # Register commands
    state.slash_commands["help"] = cmd_help
    state.slash_commands["clear"] = cmd_clear
    state.slash_commands["exit"] = cmd_exit
    state.slash_commands["quit"] = cmd_exit
    state.slash_commands["version"] = cmd_version


def handle_slash_command(state: UIState, text: str) -> bool:
    """Process slash commands and return whether to continue."""
    if not text.startswith("/"):
        return True
    parts = text[1:].split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    if cmd in state.slash_commands:
        try:
            return state.slash_commands[cmd](args)
        except Exception as e:
            msg: UIMessage = {
                "role": "system",
                "content": f"Error executing /{cmd}: {e}",
            }
            render_message(msg)
            return True
    else:
        error_msg: UIMessage = {
            "role": "system",
            "content": f"Unknown command: /{cmd}\nType /help to see available commands.",
        }
        render_message(error_msg)
        return True
