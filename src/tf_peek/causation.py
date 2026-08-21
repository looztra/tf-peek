"""Rendering of Terraform's stated causation: forcing paths, change reasons and mechanism.

Terraform states two independent signals for why a change was selected: ``replace_paths``
(the attribute paths that forced a replacement) and ``action_reason`` (a display-hint code
covering replaces, deletes and data-source reads). This module renders both into neutral
prose and decides what the report may say: which paths survive sensitivity masking, which
reason is redundant, how many paths the collapsed summary line carries.

It is a distinct discipline from ``formatting.py``, which renders attribute *values*: a path
is HCL-style attribute notation, not a JSON-encoded value, and the phrasing table interprets
Terraform's display hints without ever inferring operator intent. ``Causation`` carries
**neutral** text; the escaping functions here are registered as Jinja filters by
``report.py`` so that the context which applies an escape is the context that knows it. See
the ``plan-causation-rendering`` capability for the requirements this module implements.
"""

import html
import json
import re
from dataclasses import dataclass
from typing import Any, Final, Literal

from .diff import Marker, is_sensitive, marker_for_key

_IDENTIFIER: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")

# The one reason rendering paths makes redundant: it names the mechanism ("the provider can't
# update in place") that the paths already demonstrate. Deliberately absent from
# ``_KNOWN_REASONS``: Terraform only emits this code alongside a non-empty forcing path set, so
# the phrase would never be rendered. A pathless occurrence from some future producer degrades
# to the passthrough sentence, which is the documented behaviour for a code we cannot phrase.
_REDUNDANT_REASON: Final = "replace_because_cannot_update"

# Neutral prose for the non-"read_*" action_reason codes Terraform 1.9.5 can emit. Phrasing
# mirrors Terraform's own vocabulary and never classifies a reason as expected, unexpected,
# intentional or accidental. "read_*" codes describe data-source reads, which never reach the
# resource-change detail blocks this module renders for.
_KNOWN_REASONS: Final[dict[str, str]] = {
    "replace_because_tainted": "the resource is tainted, so Terraform planned to replace it",
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

_REPLACEMENT_REASONS: Final = frozenset(
    {
        "replace_because_tainted",
        "replace_by_request",
        "replace_by_triggers",
    }
)

# Neutral statement of the replacement mechanism. States the mechanism only: the consequence of
# destroying before creating (downtime, data loss, a new secret value) depends on the resource
# and is not knowable from the plan.
_MECHANISM_STATEMENTS: Final[dict[str, str]] = {
    "destroy_first": "the existing object is destroyed before its replacement is created",
    "create_first": "the replacement is created before the existing object is destroyed",
}

# Bounds on what the collapsed `<summary>` line shows. The count cap keeps the line scannable;
# the character budget keeps it *finite*, since a path step is an arbitrary map key and a single
# Kubernetes annotation or IAM condition key can run to hundreds of characters — three of those
# would push the resource address off screen, defeating the reason causation is on this line at
# all. Neither cap withholds information: the full sorted list always lands in the block body.
_SUMMARY_PATH_LIMIT: Final = 3
_SUMMARY_CHAR_BUDGET: Final = 120

# Inline Markdown delimiters. Numeric entities display the original character but cannot act as
# syntax. A pipe is deliberately absent: it is inert in this paragraph context and stays unchanged.
_MARKDOWN_ENTITIES: Final = str.maketrans(
    {
        "&": "&amp;",
        "<": "&lt;",
        "\\": "&#92;",
        "`": "&#96;",
        "*": "&#42;",
        "_": "&#95;",
        "[": "&#91;",
        "]": "&#93;",
        "!": "&#33;",
        "~": "&#126;",
        "$": "&#36;",
    }
)

# GitHub autolinks URLs even after entity decoding and even inside raw-HTML `<summary>` content.
# An invisible trusted HTML comment splits the parser's text node while preserving the displayed and
# copied text exactly. Mentions and issue references need the same boundary in repository context.
_GITHUB_AUTOLINK_PREFIX: Final = re.compile(r"(?i)\b(https?|ftp)(?=://)|\b(w)(?=ww\.)")
_GITHUB_REFERENCE_START: Final = re.compile(r"(?<!&)(?=[@#][A-Za-z0-9])")


def _render_step(step: object, *, first: bool) -> str:
    """Render one attribute-path step in the notation a Terraform user reads in plan output.

    A string step renders as a dotted name when it is identifier-safe and as a JSON-quoted
    subscript otherwise; an integer renders as a bracketed index. Anything else — a float, a
    null, a bool, a nested structure — renders as a JSON-encoded subscript rather than failing:
    the plan said it, so the report shows it. ``bool`` is matched before ``int`` because it is an
    ``int`` subclass, and reporting ``true`` as index ``[1]`` would state something the plan
    never contained.
    """
    if isinstance(step, str):
        if _IDENTIFIER.fullmatch(step):
            return step if first else f".{step}"
        return f"[{json.dumps(step, ensure_ascii=False)}]"
    if isinstance(step, int) and not isinstance(step, bool):
        return f"[{step}]"
    return f"[{json.dumps(step, ensure_ascii=False, default=str)}]"


def _truncate_at_masked_value(path: list[Any], markers: tuple[Marker, Marker]) -> list[Any]:
    """Reduce a forcing path to its attribute name when that attribute's value is masked.

    A forcing path names an *attribute*, not its value, so the named attribute is always
    rendered — Terraform's own output likewise annotates a forcing attribute beside a redacted
    value. But a path may descend *into* a masked value, whose map keys are part of what the
    marker covers. ``calculate_diff`` masks a whole top-level attribute as soon as any leaf
    under it is truthy, so cutting the path to that same attribute is exactly the granularity
    the table shows: a rendered path can never name something the table does not. Both sides'
    markers are consulted and the union wins, matching the fail-closed policy ``is_sensitive``
    exists to enforce.
    """
    if not path or not isinstance(path[0], str):
        return path
    if any(is_sensitive(marker_for_key(marker, path[0])) for marker in markers):
        return path[:1]
    return path


def render_forcing_path(path: list[Any]) -> str:
    """Render one forcing path in Terraform's attribute-path notation, e.g. ``settings[0].tier``."""
    return "".join(_render_step(step, first=index == 0) for index, step in enumerate(path))


def render_forcing_paths(paths: list[list[Any]], *, sensitivity: tuple[Marker, Marker] | None = None) -> list[str]:
    """Render, sort and de-duplicate forcing paths, truncating any that descend into masked values.

    Sorting the rendered strings (not the raw step arrays) keeps the sort key and the displayed
    text identical, so the same plan always produces the same report bytes regardless of the
    order or multiplicity ``replace_paths`` states them in. A path that renders to nothing — an
    empty step array — is dropped rather than emitted as empty markup. ``sensitivity`` is
    ``None`` when the caller has been told to show sensitive values.
    """
    if sensitivity is not None:
        paths = [_truncate_at_masked_value(path, sensitivity) for path in paths]
    return sorted({rendered for path in paths if (rendered := render_forcing_path(path))})


def _collapse_newlines(text: str) -> str:
    """Replace CR/LF with a visible escape so a rendered fragment stays on one physical line."""
    return text.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")


def _split_autolink_prefix(match: re.Match[str]) -> str:
    """Split one GitHub autolink prefix without changing its rendered text."""
    prefix = match.group()
    return f"{prefix[0]}<!-- -->{prefix[1:]}"


def _break_github_links(text: str) -> str:
    """Prevent GitHub autolinks, mentions and issue references in escaped plan text."""
    text = _GITHUB_AUTOLINK_PREFIX.sub(_split_autolink_prefix, text)
    return _GITHUB_REFERENCE_START.sub("<!-- -->", text)


def escape_in_code_span(text: str) -> str:
    r"""Escape a forcing path the template wraps in a Markdown code span.

    ``render_forcing_path`` JSON-encodes every non-identifier string step, so CR/LF cannot reach
    this presentation boundary. A backtick is the only remaining delimiter: CommonMark does not
    decode entities inside code spans, so it becomes literal escape text (``\u0060``).
    """
    return text.replace("`", r"\u0060")


def escape_in_markdown(text: str) -> str:
    """Escape a fragment the template emits as Markdown paragraph prose.

    HTML and inline-Markdown delimiters become entities. GitHub autolinks after entity decoding, so
    trusted invisible comments also split URL, mention and issue-reference prefixes. Both mechanisms
    preserve the displayed text; pipes remain literal because they are ordinary paragraph content.
    CR/LF collapse so the fragment cannot start a new block.
    """
    escaped = _collapse_newlines(text).translate(_MARKDOWN_ENTITIES)
    return _break_github_links(escaped)


def escape_in_html(text: str) -> str:
    """Escape a fragment the template emits inside the ``<summary>`` element.

    ``<summary>`` is raw HTML under ``autoescape=False``, so the full HTML escape set applies.
    GitHub still autolinks text inside that block; trusted invisible comments split those prefixes
    without changing rendered text. CR/LF collapse to preserve the single-line summary invariant.
    """
    return _break_github_links(html.escape(_collapse_newlines(text)))


def _reported_reason(code: str) -> str:
    """Mark a reason code as uninterpreted Terraform output."""
    return f'reason reported by Terraform: "{code}"'


def phrase_reason(code: str) -> str:
    """Phrase a stated ``action_reason`` neutrally, passing an unrecognized code through verbatim.

    Known codes map to prose that mirrors Terraform's own vocabulary without inferring intent,
    severity or expectedness. An unrecognized code is preserved behind a preamble stating it is
    Terraform's own reported output rather than tf-peek's interpretation, so a future Terraform
    release degrades a sentence instead of failing to render.
    """
    phrase = _KNOWN_REASONS.get(code)
    return phrase if phrase is not None else _reported_reason(code)


def _cap_summary_paths(paths: list[str]) -> tuple[list[str], int]:
    """Select the forcing paths the collapsed summary line shows, and count what is left over.

    Bounded by path count and by rendered characters. At least one path is always shown,
    truncated with an ellipsis if it alone exceeds the budget, so the line reports something
    concrete no matter how long a single map key is.
    """
    shown: list[str] = []
    budget = _SUMMARY_CHAR_BUDGET
    for path in paths[:_SUMMARY_PATH_LIMIT]:
        if not shown:
            shown.append(path if len(path) <= budget else f"{path[: budget - 1]}…")
        elif len(path) <= budget:
            shown.append(path)
        else:
            break
        budget -= len(shown[-1])
    return shown, len(paths) - len(shown)


@dataclass(frozen=True, slots=True)
class Causation:
    """A resource's explanation as neutral text, before any context-specific escaping.

    Every field is exactly what Terraform stated, rendered into prose and nothing more: no
    Markdown, no HTML, no escaping. The template applies the escape its own context requires and
    owns the markup, so this value is equally usable by a future JSON emitter. ``summary_paths``
    and ``summary_remainder`` carry the collapsed-line cap as data rather than as pre-joined
    text; ``mechanism`` is ``None`` for anything that is not a replacement.
    """

    paths: list[str]
    reason: str | None
    mechanism: str | None
    summary_paths: list[str]
    summary_remainder: int


def resolve_causation(
    replace_paths: list[list[Any]],
    action_reason: str | None,
    *,
    mechanism: Literal["destroy_first", "create_first"] | None,
    sensitivity: tuple[Marker, Marker] | None,
) -> Causation | None:
    """Resolve a resource's stated causation into neutral, renderable text.

    Forcing paths are rendered only for a replacement — ``mechanism`` carries that fact — because
    a forcing path explains a replacement and nothing else. Deletion reasons remain interpretable
    without a replacement mechanism. A replacement-only reason attached to any other action is
    surfaced as uninterpreted Terraform output instead of asserting a replacement that the action
    classification contradicts.

    The narrow precedence rule then applies: paths plus ``replace_because_cannot_update`` render
    as paths only, because the reason is redundant with what the paths already identify; paths
    plus any other recognized or unrecognized reason render both. ``None`` comes back when the
    change gives the report nothing to say, because a change with no stated cause gets no
    explanation rather than an invented one.
    """
    paths = render_forcing_paths(replace_paths, sensitivity=sensitivity) if mechanism is not None else []
    reason = phrase_reason(action_reason) if action_reason else None
    if mechanism is None and action_reason in _REPLACEMENT_REASONS:
        reason = _reported_reason(action_reason)
    if paths and action_reason == _REDUNDANT_REASON:
        reason = None
    if not paths and reason is None and mechanism is None:
        return None

    summary_paths, summary_remainder = _cap_summary_paths(paths)
    return Causation(
        paths=paths,
        reason=reason,
        mechanism=_MECHANISM_STATEMENTS[mechanism] if mechanism is not None else None,
        summary_paths=summary_paths,
        summary_remainder=summary_remainder,
    )
