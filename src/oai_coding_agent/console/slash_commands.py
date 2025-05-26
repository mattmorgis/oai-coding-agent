from typing import Callable

from .state import UIState
from .rendering import clear_terminal, render_message


def register_slash_commands(state: UIState) -> None:
    """Register all available slash commands on the given state."""
    state.slash_commands.clear()

    def cmd_help(args: str = "") -> bool:
        """Show help information for available commands."""
        help_text = "Available Commands:\n\n"
        for cmd, func in state.slash_commands.items():
            doc = func.__doc__ or "No description available"
            help_text += f"/{cmd} - {doc}\n"
        msg = {"role": "system", "content": help_text}
        state.messages.append(msg)
        render_message(msg)
        return True

    def cmd_clear(args: str = "") -> bool:
        """Clear the chat history."""
        state.messages.clear()
        msg = {"role": "system", "content": "Chat history has been cleared."}
        state.messages.append(msg)
        clear_terminal()
        render_message(msg)
        return True

    def cmd_exit(args: str = "") -> bool:
        """Exit the application."""
        return False

    def cmd_version(args: str = "") -> bool:
        """Show version information."""
        msg = {
            "role": "system",
            "content": "CLI Chat Version: 0.1.0\nBuilt with Rich and prompt-toolkit",
        }
        state.messages.append(msg)
        render_message(msg)
        return True

    def cmd_config(args: str = "") -> bool:
        """Show or modify configuration."""
        parts = args.split()
        if not parts:
            cfg_lines = ["Current configuration:\n"]
            for k, v in state.config.items():
                cfg_lines.append(f"{k}: {'ON' if v else 'OFF'}")
            cfg_lines.append("\nUse /config vim [on|off] to toggle Vim mode.")
            msg = {"role": "system", "content": "\n".join(cfg_lines)}
            state.messages.append(msg)
            render_message(msg)
            return True

        opt = parts[0].lower()
        val = parts[1].lower() if len(parts) > 1 else None
        if opt == "vim":
            if val in ("on", "off"):
                state.config["vim_mode"] = val == "on"
            else:
                state.config["vim_mode"] = not state.config.get("vim_mode", False)

            if state.prompt_session is not None:
                from prompt_toolkit.enums import EditingMode

                state.prompt_session.app.editing_mode = (
                    EditingMode.VI
                    if state.config["vim_mode"]
                    else EditingMode.EMACS
                )

            msg = {
                "role": "system",
                "content": (
                    "Vim mode enabled." if state.config["vim_mode"] else "Vim mode disabled."
                ),
            }
            state.messages.append(msg)
            render_message(msg)
            return True

        msg = {
            "role": "system",
            "content": f"Unknown config option: {opt}",
        }
        state.messages.append(msg)
        render_message(msg)
        return True

    # Register commands
    state.slash_commands["help"] = cmd_help
    state.slash_commands["clear"] = cmd_clear
    state.slash_commands["exit"] = cmd_exit
    state.slash_commands["quit"] = cmd_exit
    state.slash_commands["version"] = cmd_version
    state.slash_commands["config"] = cmd_config


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
            msg = {"role": "system", "content": f"Error executing /{cmd}: {e}"}
            state.messages.append(msg)
            render_message(msg)
            return True
    else:
        msg = {
            "role": "system",
            "content": f"Unknown command: /{cmd}\nType /help to see available commands.",
        }
        state.messages.append(msg)
        render_message(msg)
        return True
