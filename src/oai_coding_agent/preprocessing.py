"""
Module for preprocessing Confluence storage format documents for ingestion and embedding generation.

This includes cleaning Confluence-specific macros and XML/HTML markup, normalizing whitespace, and providing basic tokenization.
"""

import re
from html import unescape


def clean_confluence_storage_format(raw: str) -> str:
    """
    Remove Confluence-specific macros and HTML/XML tags from the raw storage format.

    Strips all <ac:structured-macro> elements (including their content),
    then removes remaining tags and unescapes HTML entities.

    Args:
        raw: Raw Confluence storage format string (HTML/XML).

    Returns:
        Plain text with macros and markup removed.
    """
    # Remove all Confluence structured macros and their content (replace with space to preserve separation)
    without_macros = re.sub(
        r"<ac:structured-macro.*?</ac:structured-macro>",
        " ",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Remove any remaining HTML/XML tags
    without_tags = re.sub(r"<[^>]+>", "", without_macros)
    # Unescape HTML entities (e.g., &amp;, &lt;)
    text = unescape(without_tags)
    return text


def normalize_whitespace(text: str) -> str:
    """
    Collapse multiple whitespace characters into single spaces and trim the text.

    Args:
        text: Text to normalize.

    Returns:
        Text with normalized whitespace.
    """
    return re.sub(r"\s+", " ", text).strip()


def tokenize_text(text: str) -> list[str]:
    """
    Simple whitespace-based tokenization.

    Args:
        text: Input text to tokenize.

    Returns:
        List of token strings.
    """
    # Split on whitespace and filter out empty tokens
    return [token for token in text.split(" ") if token]


def preprocess_confluence_document(raw: str) -> str:
    """
    Full preprocessing pipeline for Confluence documents.

    Applies cleaning of macros and markup, whitespace normalization, and returns
    the final plain-text representation ready for embedding generation.

    Args:
        raw: Raw Confluence storage format string.

    Returns:
        Cleaned and normalized plain-text string.
    """
    cleaned = clean_confluence_storage_format(raw)
    normalized = normalize_whitespace(cleaned)
    return normalized
