import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable

from textual.app import App
from textual.containers import ScrollableContainer
from textual.widget import Widget
from textual.widgets import Label


class ChatEvent(Enum):
    START_PROCESSING = "start_processing"
    THINKING = "thinking"
    PROCESSING_COMPLETE = "processing_complete"
    ERROR = "error"


class ChatCallback(ABC):
    """Abstract base class for chat callbacks."""

    @abstractmethod
    def on_event(self, event: ChatEvent, message: str) -> None:
        """Handle chat events."""
        pass


class FileLogCallback(ChatCallback):
    """Callback that logs events to a file."""

    def __init__(self, log_file: str) -> None:
        self.logger = logging.getLogger("ChatEvents")
        self.logger.setLevel(logging.INFO)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

    def on_event(self, event: ChatEvent, message: str) -> None:
        self.logger.info(f"Event: {event.value} - Message: {message}")


class TuiCallback(ChatCallback):
    """Callback that updates the Terminal UI interface."""

    def __init__(
        self,
        app: App,
        message_container: ScrollableContainer,
        create_message_func: Callable[[str, str], Label],
        live_message_widget: Widget,
    ) -> None:
        self.app = app
        self.message_container = message_container
        self.create_message = create_message_func
        self.live_message = live_message_widget

    def on_event(self, event: ChatEvent, message: str) -> None:
        def update_ui() -> None:
            # Update live message widget if available
            if self.live_message:
                if event == ChatEvent.START_PROCESSING:
                    self.live_message.show("🤔 Processing your message...")
                elif event == ChatEvent.THINKING:
                    self.live_message.show(f"💭 {message}")
                elif event == ChatEvent.ERROR:
                    self.live_message.show(f"❌ Error: {message}")
                elif event == ChatEvent.PROCESSING_COMPLETE:
                    # self.message_container.mount(self.create_message("Event", f"✅ Response ready: {message}"))
                    self.live_message.hide()

            # Log events to message container for debugging
            if event == ChatEvent.ERROR:
                self.message_container.mount(
                    self.create_message("Error", f"❌ {message}")
                )
                self.message_container.scroll_end(animate=False)

            # Force a refresh of the screen
            if self.live_message:
                self.live_message.refresh()

        # Call the UI update from the main thread
        """
        This pattern is essential because:
        - Agent processing happens in background threads
        - UI updates must be thread-safe
        - Prevents race conditions and UI corruption
        - Maintains responsiveness of the application

        The call_from_thread method essentially queues the UI update to be executed safely on the main thread, where all UI operations should occur.

        Key Reasons:
        - Thread Confinement: Most GUI frameworks (including Textual) are not thread-safe
        - Single Thread Model: UI operations must happen on the main thread
        - Race Conditions: Direct updates from background threads can corrupt UI state
        """
        self.app.call_from_thread(update_ui)
