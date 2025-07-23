import pytest

from oai_coding_agent.preprocessing import (
    clean_confluence_storage_format,
    normalize_whitespace,
    preprocess_confluence_document,
    tokenize_text,
)


def test_clean_html_tags_only() -> None:
    raw = "<p>Hello <strong>World</strong>!</p>"
    cleaned = clean_confluence_storage_format(raw)
    assert cleaned == "Hello World!"


def test_clean_confluence_code_macro() -> None:
    raw = (
        "<p>Before</p>"
        '<ac:structured-macro ac:name="code">'
        "<ac:plain-text-body><![CDATA[x = 1]]></ac:plain-text-body>"
        "</ac:structured-macro>"
        "<p>After</p>"
    )
    cleaned = clean_confluence_storage_format(raw)
    # Macro content should be removed, tags stripped, and content separated by space
    assert cleaned == "Before After"


def test_clean_confluence_panel_macro() -> None:
    raw = (
        '<ac:structured-macro ac:name="panel">'
        "<ac:rich-text-body><p>Info panel</p></ac:rich-text-body>"
        "</ac:structured-macro>"
        "Text"
    )
    cleaned = clean_confluence_storage_format(raw)
    # Panel macro and its content should be removed entirely
    assert cleaned == " Text"


def test_unescape_html_entities() -> None:
    raw = "<p>Fish &amp; Chips &lt;Delicious&gt;</p>"
    cleaned = clean_confluence_storage_format(raw)
    # HTML entities should be unescaped
    assert "Fish & Chips <Delicious>" in cleaned


def test_normalize_whitespace_collapses_and_strips() -> None:
    text = "  This  is\n a   test  "
    normalized = normalize_whitespace(text)
    assert normalized == "This is a test"


def test_tokenize_text_splits_on_spaces() -> None:
    text = "one two   three"
    tokens = tokenize_text(text)
    assert tokens == ["one", "two", "three"]


def test_preprocess_confluence_document_pipeline() -> None:
    raw = (
        "<p> Alpha &amp; Beta </p>"
        '<ac:structured-macro ac:name="code">'
        "<ac:plain-text-body><![CDATA[print(123)]]></ac:plain-text-body>"
        "</ac:structured-macro>"
        "<p>Gamma</p>"
    )
    result = preprocess_confluence_document(raw)
    # Macro removed, HTML tags stripped, entities unescaped, whitespace normalized
    assert result == "Alpha & Beta Gamma"


if __name__ == "__main__":
    pytest.main()
