from prompt_toolkit.keys import Keys

from oai_coding_agent.console.key_bindings import get_key_bindings


def test_get_key_bindings_contains_tab():
    kb = get_key_bindings()
    # Ensure we have at least one binding for Tab key
    tab_bindings = [b for b in kb.bindings if Keys.Tab in b.keys]
    assert tab_bindings, "Tab key binding should be present"


def test_ctrl_j_binding_exists():
    kb = get_key_bindings()
    # Ensure we have newline binding for Ctrl+J
    ctrl_j_bindings = [b for b in kb.bindings if "c-j" in b.keys]
    assert ctrl_j_bindings, "Ctrl+J binding should be present for newline"


def test_alt_enter_binding_exists():
    kb = get_key_bindings()
    # Ensure we have Alt+Enter binding for newline
    alt_enter_bindings = [
        b for b in kb.bindings if Keys.Escape in b.keys and Keys.Enter in b.keys
    ]
    assert alt_enter_bindings, "Alt+Enter binding should be present for newline"
