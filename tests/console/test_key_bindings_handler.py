# mypy: ignore-errors
# ruff: noqa: PLC0415

import asyncio

import pytest
from prompt_toolkit.filters import completion_is_selected, has_completions
from prompt_toolkit.key_binding.key_bindings import Binding, KeyBindings
from prompt_toolkit.keys import Keys

from oai_coding_agent.console.repl_console import KeyBindingsHandler


class DummyAgent:
    def __init__(self) -> None:
        self.cancel_called = False

    async def cancel(self) -> None:
        self.cancel_called = True


class DummyPrinter:
    def __init__(self) -> None:
        self.called = False
        self.args = None

    def __call__(self, message: str, style: str) -> None:
        self.called = True
        self.args = (message, style)


class FakeState:
    def __init__(self, completions, current):
        self.completions = completions
        self.current_completion = current
        self.complete_index = None


class FakeBuffer:
    def __init__(self, state: FakeState) -> None:
        self.complete_state = state
        self.applied = None
        self.canceled = False
        self.validated = False
        self.next_called = False
        self.inserted_text = None

    def apply_completion(self, comp):
        self.applied = comp

    def cancel_completion(self):
        self.canceled = True

    def validate_and_handle(self):
        self.validated = True

    def complete_next(self):
        self.next_called = True

    def insert_text(self, data: str) -> None:
        self.inserted_text = data


class DummyEvent:
    def __init__(self, buf):
        self.current_buffer = buf


@pytest.fixture(autouse=True)
def patch_run_in_terminal(monkeypatch):
    """Stub out run_in_terminal so key binding handlers can call printer."""
    monkeypatch.setattr(
        "oai_coding_agent.console.repl_console.run_in_terminal", lambda fn: fn()
    )


@pytest.fixture
def handler_printer_agent():
    agent = DummyAgent()
    printer = DummyPrinter()
    handler = KeyBindingsHandler(agent, printer)
    return handler, printer, agent


def find_binding(bindings: KeyBindings, key_sequence) -> Binding:
    for b in bindings.bindings:
        if tuple(b.keys) == key_sequence:
            return b
    pytest.skip(f"Binding for {key_sequence} not found")


def test_enter_with_completions(handler_printer_agent, monkeypatch):
    handler, _, agent = handler_printer_agent
    kb = handler.bindings
    binding = find_binding(kb, ("enter",))

    state = FakeState(completions=["X"], current="X")
    buf = FakeBuffer(state)
    event = DummyEvent(buf)

    # Patch filters so the enter binding is active
    monkeypatch.setattr(
        "prompt_toolkit.filters.completion_is_selected",
        lambda: False,
    )
    monkeypatch.setattr(
        "prompt_toolkit.filters.has_completions",
        lambda: True,
    )

    binding.handler(event)

    assert buf.applied == "X"
    assert buf.canceled
    assert buf.validated


def test_tab_single_and_multiple(handler_printer_agent, monkeypatch):
    handler, _, _ = handler_printer_agent
    kb = handler.bindings
    binding = find_binding(kb, ("tab",))

    # Single completion
    state1 = FakeState(completions=["A"], current="A")
    buf1 = FakeBuffer(state1)
    event1 = DummyEvent(buf1)
    # allow tab bound by has_completions
    import prompt_toolkit.filters as filters

    monkey = pytest.MonkeyPatch()
    monkey.setattr(filters, "has_completions", lambda: True)

    binding.handler(event1)
    assert buf1.applied == "A"
    assert buf1.canceled
    assert not buf1.next_called

    # Multiple completions => cycle
    state2 = FakeState(completions=["A", "B"], current=None)
    buf2 = FakeBuffer(state2)
    event2 = DummyEvent(buf2)
    binding.handler(event2)
    assert not buf2.applied
    assert buf2.next_called
    monkey.undo()


def test_ctrl_j_and_alt_enter(handler_printer_agent):
    handler, _, _ = handler_printer_agent
    kb = handler.bindings

    # Ctrl-J
    binding_j = find_binding(kb, ("c-j",))
    buf = FakeBuffer(FakeState([], None))
    event = DummyEvent(buf)
    binding_j.handler(event)
    assert buf.inserted_text == "\n"

    # Alt-Enter
    binding_alt = find_binding(kb, (Keys.Escape, Keys.Enter))
    buf2 = FakeBuffer(FakeState([], None))
    event2 = DummyEvent(buf2)
    binding_alt.handler(event2)
    assert buf2.inserted_text == "\n"


def test_escape_cancels_and_prints(handler_printer_agent):
    handler, printer, agent = handler_printer_agent
    kb = handler.bindings
    binding = find_binding(kb, ("escape",))

    buf = FakeBuffer(FakeState([], None))
    event = DummyEvent(buf)

    # Call async handler
    import asyncio

    asyncio.run(binding.handler(event))

    assert agent.cancel_called
    assert printer.called
    assert printer.args == ("error: Agent cancelled by user", "bold red")
