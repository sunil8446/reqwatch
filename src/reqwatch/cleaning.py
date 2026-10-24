"""HTML -> cleaned text.

Phase 1 storage rule: only cleaned text is stored in posting_versions.
Boilerplate stripping for token savings is Phase 2 and hooks in here
(clean_for_extraction) so both stages share one normalisation path.
"""
from __future__ import annotations

import html
import re

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]+")
_BLANK_RUN = re.compile(r"\n{3,}")


def html_to_cleaned_text(raw: str | None) -> str:
    """Convert a posting description (HTML, possibly entity-escaped) to clean text.

    Greenhouse double-escapes entities (&lt;p&gt;), so we unescape until stable
    (max 3 passes) before stripping tags.
    """
    if not raw:
        return ""
    text = raw
    for _ in range(3):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped
    # Block-level tags become line breaks so structure survives tag stripping.
    text = re.sub(r"(?i)</(p|div|li|h[1-6]|tr)>", "\n", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    lines = [_WS.sub(" ", line).strip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()


def normalize_for_hash(title: str, location: str | None, department: str | None, cleaned_text: str) -> str:
    """Canonical string that gets hashed for change detection.

    Normalisation is deliberately conservative: casefold + whitespace collapse,
    so a whitespace-only re-render by the ATS does not create a new SCD2 version,
    while any real wording change does.
    """
    parts = [
        (title or "").strip().casefold(),
        (location or "").strip().casefold(),
        (department or "").strip().casefold(),
        _WS.sub(" ", cleaned_text).strip().casefold(),
    ]
    return "\n".join(parts)
