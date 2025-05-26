from prompt_toolkit.keys import Keys

from oai_coding_agent.console.key_bindings import get_key_bindings


def test_get_key_bindings_contains_tab():
    kb = get_key_bindings()
    # Ensure we have at least one binding for Tab key
    tab_bindings = [b for b in kb.bindings if Keys.Tab in b.keys]
    assert tab_bindings, "Tab key binding should be present"
