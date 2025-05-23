import asyncio
import os
import random
from typing import Callable, Dict, List

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Heading, Markdown
from rich.panel import Panel


# Classes to override the hideous default Markdown renderer
class PlainHeading(Heading):
    """Left-aligned, no panel."""

    def __rich_console__(self, console, options):
        self.text.justify = "left"  # don’t centre
        yield self.text  # just emit the raw Text


class PlainMarkdown(Markdown):
    elements = Markdown.elements.copy()
    elements["heading_open"] = PlainHeading  # swap it in


Markdown.elements["heading_open"] = PlainHeading

console = Console()

messages: List[dict] = []
thinking_active = False

slash_commands: Dict[str, Callable] = {}


def clear_terminal():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def render_messages():
    """Render all messages in the chat history."""
    # Clear the screen to simulate a TUI
    clear_terminal()

    # Print each message with appropriate styling
    for msg in messages:
        if msg["role"] == "user":
            console.print(f"[bold blue]You:[/bold blue] {msg['content']}")
            console.print()
        elif msg["role"] == "assistant":
            console.print("[bold green]Assistant:[/bold green]")
            # Create custom markdown with our own heading styles
            content = msg["content"]
            md = Markdown(
                content,
                code_theme="nord",
                hyperlinks=True,
                inline_code_lexer="python",
            )
            console.print(md)
            console.print()
        elif msg["role"] == "thinking":
            console.print(f"[yellow]{msg['content']}[/yellow]")
            console.print()
        elif msg["role"] == "system":
            # System messages with more subtle styling
            console.print(
                f"[dim yellow]System:[/dim yellow] [yellow]{msg['content']}[/yellow]"
            )
            console.print()


async def animate_thinking():
    """Animate the thinking indicator."""
    global thinking_active
    thinking_states = ["🤔 Thinking.", "🤔 Thinking..", "🤔 Thinking..."]
    thinking_index = 0

    # Find the thinking message index
    thinking_idx = next(
        (i for i, msg in enumerate(messages) if msg["role"] == "thinking"), None
    )

    if thinking_idx is None:
        return

    while thinking_active:
        messages[thinking_idx]["content"] = thinking_states[thinking_index]
        thinking_index = (thinking_index + 1) % len(thinking_states)
        render_messages()
        await asyncio.sleep(0.5)


async def get_ai_response(user_message: str) -> str:
    """Generate an AI response (mock implementation)."""
    # Simulate AI thinking time
    await asyncio.sleep(random.uniform(1.5, 3))

    # Generate mock response based on input
    user_lower = user_message.lower()

    # Code-related responses
    if any(
        word in user_lower for word in ["code", "python", "function", "class", "import"]
    ):
        return """Here's a simple Python example:

```python
def greet(name):
    return f"Hello, {name}!"

print(greet("World"))
```

This function takes a name parameter and returns a greeting. Pretty straightforward!"""

    # Math/calculation responses
    elif any(
        word in user_lower
        for word in ["calculate", "math", "number", "+", "-", "*", "/"]
    ):
        return "I'd need to think about that calculation. For complex math, I'd typically break it down step by step and show my work. What specific calculation did you have in mind?"

    # Help/how-to responses
    elif any(
        word in user_lower for word in ["how", "help", "explain", "what is", "tell me"]
    ):
        return """# Great question!

I'd be happy to help explain that. Here's a breakdown:

## Key Concepts
- First important point
- Second important point
- Third important point

### Example
Here's a practical example that illustrates the concept:

```python
def example_function():
    \"""This demonstrates the concept we're discussing\"""
    result = [x for x in range(10) if x % 2 == 0]
    return result

# This would return: [0, 2, 4, 6, 8]
```

Hope this helps! *Let me know* if you need **more details**."""

    # Short responses for greetings
    elif any(
        word in user_lower
        for word in ["hello", "hi", "hey", "good morning", "good afternoon"]
    ):
        greetings = [
            "Hello there! How can I help you today?",
            "Hi! What would you like to chat about?",
            "Hey! I'm here and ready to assist.",
            "Good to see you! What's on your mind?",
        ]
        return random.choice(greetings)

    # Default varied responses
    else:
        responses = [
            f"That's an interesting point about '{user_message}'. In a real AI system, I would analyze this more deeply and provide specific insights based on my training data.",
            f"You mentioned: '{user_message}'. This reminds me of several related concepts I could explore. What aspect interests you most?",
            f"I understand you're asking about '{user_message}'. Let me think through this systematically and provide you with a thoughtful response.",
            f"Thanks for bringing up '{user_message}'. This is the kind of topic where I'd typically provide multiple perspectives and examples to give you a comprehensive answer.",
            "That's a great question! In a production AI system, I'd draw from my knowledge base to give you detailed, accurate information. For now, I'm just a friendly mock assistant! 😊",
        ]
        return random.choice(responses)


# Define slash commands
def register_slash_commands():
    """Register all available slash commands."""
    global slash_commands

    # Clear existing commands (in case this is called multiple times)
    slash_commands = {}

    def cmd_help(args=""):
        """Show help information for available commands."""
        help_text = "Available Commands:\n\n"
        for cmd, func in slash_commands.items():
            doc = func.__doc__ or "No description available"
            help_text += f"/{cmd} - {doc}\n"

        messages.append({"role": "system", "content": help_text})
        return True

    def cmd_clear(args=""):
        """Clear the chat history."""
        global messages
        messages = []
        messages.append({"role": "system", "content": "Chat history has been cleared."})
        return True

    def cmd_exit(args=""):
        """Exit the application."""
        console.print("[yellow]Goodbye![/yellow]")
        return False  # Signal to exit the main loop

    def cmd_version(args=""):
        """Show version information."""
        messages.append(
            {
                "role": "system",
                "content": "CLI Chat Version: 0.1.0\nBuilt with Rich and prompt-toolkit",
            }
        )
        return True

    # Register all commands
    slash_commands["help"] = cmd_help
    slash_commands["clear"] = cmd_clear
    slash_commands["exit"] = cmd_exit
    slash_commands["quit"] = cmd_exit
    slash_commands["version"] = cmd_version


def handle_slash_command(command_text):
    """Process slash commands and return whether to continue the main loop."""
    # Strip the leading slash
    if not command_text.startswith("/"):
        return True

    # Parse command and arguments
    parts = command_text[1:].split(maxsplit=1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""

    # Debug info
    console.print(f"[dim]DEBUG: Command '{cmd}' with args '{args}'[/dim]")
    console.print(
        f"[dim]DEBUG: Available commands: {list(slash_commands.keys())}[/dim]"
    )

    if cmd in slash_commands:
        try:
            return slash_commands[cmd](args)
        except Exception as e:
            messages.append(
                {
                    "role": "system",
                    "content": f"Error executing command /{cmd}: {str(e)}",
                }
            )
            return True
    else:
        messages.append(
            {
                "role": "system",
                "content": f"Unknown command: /{cmd}\nType /help to see available commands.",
            }
        )
        return True


async def main():
    """Main application loop."""
    global thinking_active

    # Register slash commands
    register_slash_commands()

    # Create custom key bindings to handle suggestion acceptance with Tab
    kb = KeyBindings()

    @kb.add(Keys.Tab)
    def _(event):
        """Accept auto-suggestion with tab key."""
        buffer = event.current_buffer
        suggestion = buffer.suggestion
        if suggestion:
            buffer.insert_text(suggestion.text)
        else:
            # Fall back to completion if no suggestion
            buffer.complete_next()

    # Set up prompt toolkit with history
    history_file = os.path.expanduser("~/.ai_chat_history")
    session = PromptSession(
        history=FileHistory(history_file),
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
        complete_while_typing=True,
        completer=WordCompleter([f"/{cmd}" for cmd in slash_commands]),
        complete_in_thread=True,
        key_bindings=kb,
        style=Style.from_dict(
            {
                # Input prompt styling
                "prompt": "ansicyan bold",
                # Style for auto-suggestions
                "auto-suggestion": "#888888",
            }
        ),
    )

    # Add welcome message
    messages.append(
        {
            "role": "assistant",
            "content": "Hello! I'm your AI coding assistant. How can I help you today?\n\nType `/help` to see available commands.",
        }
    )

    # Render initial state
    render_messages()

    # Main interaction loop
    continue_loop = True
    while continue_loop:
        try:
            # Get user input with prompt-toolkit
            # Print a newline and reset the line for clean input
            console.print()

            # Use prompt_toolkit with a simple '>' prompt
            user_input = await asyncio.to_thread(lambda: session.prompt("› "))

            # Show the input with a border
            console.print(Panel(user_input, border_style="cyan", expand=False))

            if not user_input.strip():
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                continue_loop = handle_slash_command(user_input)
                render_messages()
                continue

            # Add user message
            messages.append({"role": "user", "content": user_input})

            # Add thinking indicator
            messages.append({"role": "thinking", "content": "🤔 Thinking..."})
            thinking_active = True

            # Start thinking animation
            thinking_task = asyncio.create_task(animate_thinking())

            # Get AI response (non-blocking)
            response = await get_ai_response(user_input)

            # Stop thinking animation
            thinking_active = False
            await thinking_task

            # Remove thinking message
            messages.pop()

            # Add assistant response
            messages.append({"role": "assistant", "content": response})

            # Render the updated messages
            render_messages()

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            continue_loop = False
        except EOFError:
            # Handle Ctrl+D gracefully
            continue_loop = False


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting...[/yellow]")
