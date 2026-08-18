"""Rendering of semantic diff values into Markdown table cells."""

import json

from .diff import DisplaySentinel, ReportValue


def _json_default(obj: object) -> str:
    """Serialize a ``_DisplaySentinel`` as its text so it renders inside JSON."""
    if isinstance(obj, DisplaySentinel):
        return obj.text
    msg = f"not JSON serializable: {type(obj).__name__}"
    raise TypeError(msg)


def format_report_value(value: ReportValue) -> str:
    r"""Format a diff value for a single Markdown resource-details table cell.

    Display sentinels (sensitive-value and known-after-apply markers) render as
    their bare human-readable text. Every other value renders as JSON with ``|``
    escaped as ``\u007c`` and backticks as ``\u0060`` so the cell cannot gain a
    phantom table column or close its code-span wrapper: dicts and lists as
    compact objects/arrays that round-trip through ``json.loads``, strings as
    quoted literals (so a string ``"false"`` stays distinct from a boolean
    ``false`` and an empty string stays visible), and other scalars (``null``,
    booleans, numbers) as their bare JSON literal. The two escapes are no-ops for
    scalars, which cannot contain either delimiter.
    """
    if isinstance(value, DisplaySentinel):
        return value.text
    return json.dumps(value, ensure_ascii=False, default=_json_default).replace("|", r"\u007c").replace("`", r"\u0060")
