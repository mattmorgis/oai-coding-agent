import asyncio

from rich.markdown import Markdown
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.widgets import Collapsible, Input, LoadingIndicator, Static


class UserPrompt(Message):
    def __init__(self, text: str):
        super().__init__()
        self._text = text

    @property
    def text(self) -> str:
        return self._text


class Thought(Message):
    pass


class Final(Message):
    pass


class ChatApp(App):
    def compose(self) -> ComposeResult:
        self.chat = ScrollView()
        yield self.chat
        yield Input(placeholder="Let's plan a feature together...", id="input").focus()

    def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        self.post_message(UserPrompt(text))

    def action_submit(self):
        prompt_widigt = self.query_one("#prompt", Input)
        if not prompt_widigt.value.strip():
            return
        text = prompt_widigt.value
        prompt_widigt.value = ""
        self.post_message(UserPrompt(text))

    def on_user_prompt(self, message: UserPrompt):
        self.chat.mount(Static(f"[bold]you > [/] {message.text}"))
        spinner = LoadingIndicator()
        thoughts_box = Static("", classes="thoughts")
        container = Vertical(spinner, thoughts_box)
        self.chat.mount(container)
        self.auto_scroll()
        self.run_worker(self.agent_run(message.text, spinner, thoughts_box, container))

    async def agent_run(self, prompt, spinner, thoughts_box, container):
        thoughts = []
        async for event in fake_agent_stream(prompt):  # replace with real stream
            if event["type"] == "thought":
                thoughts.append(event["text"])
                thoughts_box.update(event["text"])  # "replace" mode
                self.auto_scroll()
        final_answer = event["final"]
        # 4. cleanup UI on finish
        spinner.remove()
        container.remove()  # drop live box
        self.chat.mount(
            Collapsible(
                Static("\n".join(thoughts)),
                collapsed=True,
            )
        )
        self.chat.mount(Static(Markdown(final_answer)))
        self.auto_scroll()

    def auto_scroll(self):  # keep bottom in view
        self.chat.scroll_end(animate=False)


async def fake_agent_stream(prompt):
    for i in range(3):
        await asyncio.sleep(0.8)
        yield {"type": "thought", "text": f"thinking #{i + 1}…"}
    await asyncio.sleep(1)
    yield {"type": "final", "final": f"**Done!** Your prompt was: `{prompt}`"}
