"""Rendering of Terraform's stated causation: forcing paths, change reasons and mechanism.

Terraform states two independent signals for why a change was selected: ``replace_paths``
(the attribute paths that forced a replacement) and ``action_reason`` (a display-hint code
covering replaces, deletes and data-source reads). This module renders both into neutral,
escaped prose. It is a distinct discipline from ``formatting.py``, which renders attribute
*values*: a path is HCL-style attribute notation, not a JSON-encoded value, and the phrasing
table interprets Terraform's display hints without ever inferring operator intent. See the
``plan-causation-rendering`` capability for the requirements this module implements.
"""

import json
import re
from dataclasses import dataclass
from typing import Final

_IDENTIFIER: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")

# The one reason rendering paths already makes redundant: it names the mechanism ("the
# provider can't update in place") that the paths already demonstrate.
_REDUNDANT_REASON: Final = "replace_because_cannot_update"

# Neutral prose for every non-"read_*" action_reason code Terraform 1.9.5 can emit. Phrasing
# mirrors Terraform's own vocabulary and never classifies a reason as expected, unexpected,
# intentional or accidental. "read_*" codes describe data-source reads, which never reach the
# resource-change detail blocks this module renders for.
_KNOWN_REASONS: Final[dict[str, str]] = {
    "replace_because_tainted": "the resource is tainted, so Terraform planned to replace it",
    "replace_because_cannot_update": (
        "the provider reported that this change cannot be made without replacing the object"
    ),
    "replace_by_request": "the replacement was explicitly requested when the plan was created",
    "replace_by_triggers": "configured replacement triggers selected the replacement",
    "delete_because_no_resource_config": "Terraform found no corresponding resource configuration",
    "delete_because_wrong_repetition": (
        "the resource's addressing mode (count, for_each, or neither) no longer matches its configuration"
    ),
    "delete_because_count_index": "the resource's count index is out of range for the currently configured count",
    "delete_because_each_key": "the resource's for_each key no longer matches",
    "delete_because_no_module": "the resource's containing module instance is no longer declared",
    "delete_because_no_move_target": "the resource is the target of a moved block with no corresponding configuration",
}

# Bound on how many forcing paths the collapsed `<summary>` line shows; the display cap never
# withholds information because the full, sorted list always lands in the detail block body.
_SUMMARY_PATH_LIMIT: Final = 3


def _render_step(step: str | int, *, first: bool) -> str:
    """Render one attribute-path step in the notation a Terraform user reads in plan output."""
    if isinstance(step, int):
        return f"[{step}]"
    if _IDENTIFIER.fullmatch(step):
        return step if first else f".{step}"
    return f"[{json.dumps(step, ensure_ascii=False)}]"


def render_forcing_path(path: list[str | int]) -> str:
    """Render one forcing path in Terraform's attribute-path notation, e.g. ``settings[0].tier``."""
    return "".join(_render_step(step, first=index == 0) for index, step in enumerate(path))


def render_forcing_paths(paths: list[list[str | int]]) -> list[str]:
    """Render, sort and de-duplicate forcing paths by their rendered form.

    Sorting the rendered strings (not the raw step arrays) keeps the sort key and the displayed
    text identical, so the same plan always produces the same report bytes regardless of the
    order or multiplicity ``replace_paths`` states them in.
    """
    return sorted({render_forcing_path(path) for path in paths})


def _collapse_newlines(text: str) -> str:
    """Replace CR/LF with a visible escape so a rendered fragment stays on one physical line."""
    return text.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")


def escape_for_markdown(text: str) -> str:
    r"""Escape a causation fragment for the Markdown detail-block body.

    Mirrors the discipline ``format_report_value`` applies to values: ``|`` becomes
    ``\u007c`` (cannot add a phantom table column) and a backtick becomes ``\u0060`` (cannot
    close the wrapping code span), both replaced with literal escape *text* rather than the
    character itself so the substitution is inert regardless of Markdown context. CR/LF collapse
    to a visible ``\n`` so the fragment can never break a row, or the block, across lines.
    """
    return _collapse_newlines(text).replace("|", r"\u007c").replace("`", r"\u0060")


def escape_for_summary_html(text: str) -> str:
    """Escape a causation fragment for the ``<summary>`` HTML context.

    ``<summary>`` is rendered as raw HTML under ``autoescape=False``; a stray ``<``, ``&`` or
    ``"`` there could inject markup or corrupt the enclosing tag, and CR/LF would break the
    "collapsed line" invariant the same way it would in the Markdown body.
    """
    text = _collapse_newlines(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def phrase_reason(code: str) -> str:
    """Phrase a stated ``action_reason`` neutrally, passing an unrecognized code through verbatim.

    Known codes map to prose that mirrors Terraform's own vocabulary without inferring intent,
    severity or expectedness. An unrecognized code is preserved behind a preamble stating it is
    Terraform's own reported output rather than tf-peek's interpretation, so a future Terraform
    release degrades a sentence instead of failing to render.
    """
    phrase = _KNOWN_REASONS.get(code)
    if phrase is not None:
        return phrase
    return f'reason reported by Terraform: "{code}"'


def mechanism_statement(*, destroy_before_create: bool) -> str:
    """State which replacement mechanism Terraform will use, without asserting a consequence.

    The consequence of destroying before creating (downtime, data loss, a new secret value)
    depends on the resource and is not knowable from the plan, so only the mechanism is stated.
    """
    if destroy_before_create:
        return "the existing object is destroyed before its replacement is created"
    return "the replacement is created before the existing object is destroyed"


def _render_summary_html(paths: list[str], reason: str | None) -> str:
    """Compose the ``<summary>`` line's short form: capped paths, a remainder note, the reason."""
    fragments: list[str] = []
    if paths:
        shown = paths[:_SUMMARY_PATH_LIMIT]
        codes = ", ".join(f"<code>{escape_for_summary_html(path)}</code>" for path in shown)
        remainder = len(paths) - len(shown)
        if remainder:
            codes += f" (+{remainder} more)"
        fragments.append(f"forces replacement: {codes}")
    if reason:
        fragments.append(escape_for_summary_html(reason))
    return "; ".join(fragments)


@dataclass(frozen=True, slots=True)
class Causation:
    """A resource's rendered explanation, ready for both report contexts.

    ``body_paths`` and ``body_reason`` are Markdown-escaped, unwrapped fragments for the detail
    block's body; the template wraps each path in backticks the same way it wraps attribute
    values. ``summary_html`` is a single, already-escaped and ``<code>``-wrapped HTML fragment
    ready to drop directly into the ``<summary>`` line.
    """

    body_paths: list[str]
    body_reason: str | None
    summary_html: str


def resolve_causation(replace_paths: list[list[str | int]], action_reason: str | None) -> Causation | None:
    """Resolve a resource's stated forcing paths and reason into a rendered ``Causation``.

    Applies the narrow precedence rule: paths plus ``replace_because_cannot_update`` render as
    paths only, because the reason is redundant with what the paths already identify; paths plus
    any other recognized or unrecognized reason render both; a reason without paths renders the
    reason; neither renders ``None``, because a change with no stated cause gets no explanation
    rather than an invented one.
    """
    paths = render_forcing_paths(replace_paths)
    reason = phrase_reason(action_reason) if action_reason is not None else None
    if paths and action_reason == _REDUNDANT_REASON:
        reason = None
    if not paths and reason is None:
        return None

    return Causation(
        body_paths=[escape_for_markdown(path) for path in paths],
        body_reason=escape_for_markdown(reason) if reason is not None else None,
        summary_html=_render_summary_html(paths, reason),
    )
