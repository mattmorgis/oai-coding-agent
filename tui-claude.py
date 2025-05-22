import asyncio
import random

from rich.markdown import Markdown
from textual.app import App, ComposeResult
from textual.containers import Vertical, ScrollableContainer
from textual.widgets import Footer, Input, Static


class ChatApp(App):
    CSS = """
    .message {
        margin: 1 0;
    }

    .user-message {
        color: #5f9cf7;
    }

    .assistant-message {
        color: #28a745;
    }

    .thinking {
        color: #6c757d;
        text-style: italic;
    }

    .markdown {
        margin-left: 2;
    }

    #chat-view {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        # yield Header()
        with Vertical():
            yield ScrollableContainer(id="chat-view")
            yield Input(
                placeholder="Type your message and press Enter...", id="input-box"
            ).focus()
        yield Footer()

    def on_mount(self) -> None:
        """Add a welcome message when the app starts."""
        self.add_message(
            "Hello! I'm a mock AI assistant. Try asking me something!", "assistant"
        )

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        if not event.value.strip():
            return

        # Add user message
        self.add_message(event.value, "user")

        # Clear input
        event.input.value = ""

        # Show thinking indicator
        thinking_widget = self.add_message("🤔 Thinking...", "thinking")

        # Get AI response asynchronously
        await self.get_ai_response(event.value, thinking_widget)

    def add_message(self, content: str, sender: str) -> Static:
        """Add a message to the chat view."""
        chat_view = self.query_one("#chat-view")

        if sender == "user":
            prefix = "You: "
            message_class = "user-message"
            # User messages don't need markdown rendering
            message_content = f"{prefix}{content}"
        elif sender == "thinking":
            prefix = ""
            message_class = "thinking"
            message_content = content
        else:  # assistant
            prefix = "Assistant: "
            message_class = "assistant-message"
            # Render assistant responses as markdown
            # We'll keep the prefix as plain text
            message_content = f"{prefix}{content}"
            if "```" in content or "*" in content or "#" in content:
                # Use markdown rendering for code blocks and formatting
                message_content = f"{prefix}"
                message_widget = Static(
                    message_content, classes=f"message {message_class}"
                )
                chat_view.mount(message_widget)
                # Add markdown content as a separate widget
                markdown_widget = Static(
                    Markdown(content), classes=f"markdown {message_class}"
                )
                chat_view.mount(markdown_widget)
                # Scroll to the bottom
                chat_view.scroll_end()
                return message_widget

        message_widget = Static(message_content, classes=f"message {message_class}")
        chat_view.mount(message_widget)
        # Scroll to the bottom
        chat_view.scroll_end()
        return message_widget

    def auto_scroll(self):
        """Scroll chat view to the bottom."""
        chat_view = self.query_one("#chat-view")
        chat_view.scroll_end(animate=False)

    async def get_ai_response(self, user_message: str, thinking_widget: Static) -> None:
        """Mock AI response with realistic delay and varied responses."""

        # Simulate processing time (1-3 seconds)
        await asyncio.sleep(random.uniform(1, 3))

        # Generate mock response based on input
        response = self._generate_mock_response(user_message)

        # Remove thinking indicator
        thinking_widget.remove()

        # Add AI response
        self.add_message(response, "assistant")

    def _generate_mock_response(self, user_message: str) -> str:
        """Generate varied mock responses based on user input."""
        user_lower = user_message.lower()

        # Code-related responses
        if any(
            word in user_lower
            for word in ["code", "python", "function", "class", "import"]
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
            word in user_lower
            for word in ["how", "help", "explain", "what is", "tell me"]
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


if __name__ == "__main__":
    app = ChatApp()
    app.run()
