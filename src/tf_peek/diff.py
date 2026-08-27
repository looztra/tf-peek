"""Semantic diffing of Terraform before/after values and their markers."""

from typing import Any

Marker = bool | dict[str, Any] | list[Any] | None


class DisplaySentinel:
    """A human-readable display marker carried in the semantic value tree.

    Distinct from a plain ``str`` so ``format_report_value`` can render it
    verbatim (bare, unquoted) while data strings render as JSON-quoted values,
    and so a future path-level differ can detect unknown/masked leaves
    structurally rather than by string-comparing against sentinel text.
    """

    __slots__ = ("text",)

    def __init__(self, text: str) -> None:
        """Store the human-readable marker text."""
        self.text = text

    def __eq__(self, other: object) -> bool:
        """Compare equal to another ``DisplaySentinel`` with the same text."""
        return isinstance(other, DisplaySentinel) and other.text == self.text

    def __hash__(self) -> int:
        """Hash consistently with ``__eq__``, keyed on the marker text."""
        return hash((type(self).__name__, self.text))

    def __repr__(self) -> str:
        """Return a debug repr showing the marker text."""
        return f"{type(self).__name__}({self.text!r})"


# The value domain at the presentation boundary: everything the semantic diff
# tree can hold once markers are resolved. Every resolver, ``calculate_diff``
# and ``format_report_value`` are annotated with it, so a type checker — not a
# runtime guard — is what keeps ``_Missing`` out of the formatter.
ReportValue = str | int | float | bool | None | DisplaySentinel | dict[str, "ReportValue"] | list["ReportValue"]


KNOWN_AFTER_APPLY = DisplaySentinel("(known after apply) ⏳")
SENSITIVE_VALUE = DisplaySentinel("(sensitive value)")


class _Missing:
    """A position with no concrete counterpart, distinct from any Terraform value.

    Reached when a key is absent from ``after``, or when a container marker
    extends past the concrete container. It carries its own type rather than
    being a bare ``object()`` so ``_Resolved`` can name it and every narrowing
    site is checked.
    """

    __slots__ = ()


_MISSING = _Missing()

# What a resolver returns: a report value, or absence. ``_resolve_present`` and
# ``calculate_diff`` are the only places absence is collapsed, and both hand
# back a plain ``ReportValue``.
_Resolved = ReportValue | _Missing


def is_sensitive(marker: Marker) -> bool:
    """Return True if any leaf of a Terraform sensitivity marker is truthy.

    Deliberately truthy rather than ``is True``: an unexpected marker shape must
    fail closed and mask the attribute rather than render a secret in plaintext.
    """
    if isinstance(marker, dict):
        return any(is_sensitive(v) for v in marker.values())
    if isinstance(marker, list):
        return any(is_sensitive(v) for v in marker)
    return bool(marker)


def marker_for_key(marker: Marker, key: str) -> Marker:
    """Look up the sensitivity marker for a single top-level key.

    Terraform emits per-attribute markers as a dict, but the whole ``before_sensitive``/
    ``after_sensitive`` value may instead be a bare ``bool`` (the whole object is
    sensitive) — in that case every key inherits it rather than being looked up.
    """
    return marker.get(key) if isinstance(marker, dict) else marker


def _resolve_marker_only(marker: Marker) -> _Resolved:
    """Resolve a marker for a position that has no concrete counterpart.

    A ``true`` leaf materializes as the known-after-apply sentinel. A dict
    marker keeps only truthy descendants, visited in sorted key order for
    deterministic output; an empty result signals absence via ``_MISSING``. A
    list marker preserves positional gaps as ``null`` up to the last meaningful
    index and drops trailing non-meaningful markers; an all-non-meaningful list
    signals absence. ``false``/``none``/other scalars signal absence.
    """
    if marker is True:
        return KNOWN_AFTER_APPLY
    if isinstance(marker, dict):
        result: dict[str, ReportValue] = {}
        for key in sorted(marker):
            child = _resolve_marker_only(marker[key])
            if not isinstance(child, _Missing):
                result[key] = child
        return result or _MISSING
    if isinstance(marker, list):
        materialized: list[ReportValue] = []
        last_present = -1
        for item in marker:
            child = _resolve_marker_only(item)
            if isinstance(child, _Missing):
                # Positional gap: a later meaningful index must keep its
                # position, so hold the slot with null. This synthetic null is
                # indistinguishable from a Terraform-planned null in the
                # rendered JSON by design — a positional list has no
                # marker-only way to express "no value here".
                materialized.append(None)
            else:
                materialized.append(child)
                last_present = len(materialized) - 1
        if last_present < 0:
            return _MISSING
        return materialized[: last_present + 1]
    return _MISSING


def _resolve_after_unknown(value: ReportValue, marker: Marker) -> _Resolved:
    """Recursively substitute ``after_unknown`` markers into a concrete ``after`` value.

    A ``true`` marker replaces the position with the known-after-apply sentinel. A
    dict marker recurses by key, keeping the concrete value's key order and
    appending marker-only keys in sorted order; a marker-only key surfaces only
    if its subtree contains a ``true`` leaf. A list marker recurses by index for
    existing elements, then extends with a marker-only tail. A dict/list marker
    paired with a non-dict/non-list, non-null concrete value (shape mismatch)
    leaves that concrete value unchanged. Any other marker (``false``/``none``)
    keeps the position as it is.
    """
    if marker is True:
        return KNOWN_AFTER_APPLY
    if marker is None or marker is False:
        return value
    if isinstance(marker, dict):
        return _resolve_dict_marker(value, marker)
    if isinstance(marker, list):
        return _resolve_list_marker(value, marker)
    return value


def _resolve_present(value: ReportValue, marker: Marker) -> ReportValue:
    """Resolve a marker against a position the plan actually contains.

    Absence is not representable for a value that exists, so a marker carrying
    no unknown leaf retains ``value`` — including a concrete ``null``, which
    must stay visible in the rendered cell instead of being dropped. This is the
    resolver family's only narrowing from ``_Resolved`` to ``ReportValue``,
    which is what keeps ``_MISSING`` out of the formatter.
    """
    resolved = _resolve_after_unknown(value, marker)
    return value if isinstance(resolved, _Missing) else resolved


def _resolve_dict_marker(value: ReportValue, marker: dict[str, Any]) -> _Resolved:
    """Apply a dict ``after_unknown`` marker to a concrete value."""
    if value is None:
        return _resolve_marker_only(marker)
    if not isinstance(value, dict):
        return value
    # Concrete keys keep the plan's order so both cells of a row stay
    # comparable; marker-only keys are appended in sorted order, the only place
    # this transformation invents an ordering.
    result: dict[str, ReportValue] = {key: _resolve_present(child, marker.get(key)) for key, child in value.items()}
    for key in sorted(set(marker) - set(value)):
        extra = _resolve_marker_only(marker[key])
        if not isinstance(extra, _Missing):
            result[key] = extra
    return result


def _resolve_list_marker(value: ReportValue, marker: list[Any]) -> _Resolved:
    """Apply a list ``after_unknown`` marker to a concrete value."""
    if value is None:
        return _resolve_marker_only(marker)
    if not isinstance(value, list):
        return value
    resolved: list[ReportValue] = [
        _resolve_present(item, marker[i] if i < len(marker) else None) for i, item in enumerate(value)
    ]
    tail = _resolve_marker_only(marker[len(value) :])
    if isinstance(tail, list):
        resolved.extend(tail)
    return resolved


def calculate_diff(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    unknown: Marker = None,
    before_sensitive: Marker = None,
    after_sensitive: Marker = None,
) -> dict[str, dict[str, ReportValue]]:
    """Compare before/after and handle 'known after apply' values.

    Returns:
        A dict of changed attributes keyed by attribute name, in ascending lexical
        key order. The Jinja2 report template consumes this dict via ``.items()``
        and relies on that order for deterministic Markdown output — do not
        replace the sorted traversal with a hash-ordered one (e.g. iterating a
        ``set`` or unsorted ``dict`` union) without preserving the guarantee.
    """
    diff: dict[str, dict[str, ReportValue]] = {}
    before = before or {}
    after = after or {}
    # Terraform emits ``after_unknown`` as a bare ``false`` when nothing is
    # unknown (e.g. a destroy) and an object mapping attribute names to markers
    # otherwise. Normalize to a per-key dict: ``true`` marks every known key
    # unknown; any other non-dict shape carries no marker.
    if unknown is True:
        unknown_map: dict[str, Any] = dict.fromkeys(set(before) | set(after), True)
    elif isinstance(unknown, dict):
        unknown_map = unknown
    else:
        unknown_map = {}

    all_keys = set(before.keys()) | set(after.keys()) | set(unknown_map.keys())

    for k in sorted(all_keys):
        val_before: ReportValue = before.get(k)
        marker = unknown_map.get(k)
        if k in after:
            val_after = _resolve_present(after[k], marker)
        else:
            # No concrete counterpart: surface a marker-only unknown subtree if
            # one exists, otherwise report the attribute as absent.
            resolved = _resolve_marker_only(marker)
            val_after = None if isinstance(resolved, _Missing) else resolved

        if val_before != val_after:
            if is_sensitive(marker_for_key(before_sensitive, k)) or is_sensitive(marker_for_key(after_sensitive, k)):
                val_before = SENSITIVE_VALUE
                val_after = SENSITIVE_VALUE
            diff[k] = {"before": val_before, "after": val_after}
    return diff
