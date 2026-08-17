"""Main CLI entrypoint for tf-peek."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import typer
from jinja2 import Environment, FileSystemLoader

from .config import load_config, resolve_tier
from .models import TerraformPlan

app = typer.Typer()


def get_emoji(action: str) -> str:
    """Return an emoji representation of a terraform action."""
    mapping = {"create": "➕", "update": "🛠️", "delete": "➖", "replace": "⚠️", "no-op": "🔹"}  # noqa: RUF001
    return mapping.get(action, "❓")


_Marker = bool | dict[str, Any] | list[Any] | None


class _DisplaySentinel:
    """A human-readable display marker carried in the semantic value tree.

    Distinct from a plain ``str`` so ``_format_report_value`` can render it
    verbatim (bare, unquoted) while data strings render as JSON-quoted values,
    and so a future path-level differ can detect unknown/masked leaves
    structurally rather than by string-comparing against sentinel text.
    """

    __slots__ = ("text",)

    def __init__(self, text: str) -> None:
        """Store the human-readable marker text."""
        self.text = text

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _DisplaySentinel) and other.text == self.text

    def __hash__(self) -> int:
        return hash(("_DisplaySentinel", self.text))

    def __repr__(self) -> str:
        return f"_DisplaySentinel({self.text!r})"


# A value that flows through the semantic diff tree and reaches the formatter.
# Includes the display sentinels so the type documents the full value domain at
# the presentation boundary (earning the alias: every function that touches a
# report value uses it, not bare ``Any``).
_ReportValue = str | int | float | bool | None | _DisplaySentinel | dict[str, "_ReportValue"] | list["_ReportValue"]


_KNOWN_AFTER_APPLY = _DisplaySentinel("(known after apply) ⏳")
_SENSITIVE_VALUE = _DisplaySentinel("(sensitive value)")

# Placeholder for a position with no concrete counterpart: a key absent from
# ``after`` (or an explicit ``null``), or a container marker that extends past
# the concrete container. Distinct from any real Terraform value.
_MISSING = object()


def _is_sensitive(marker: _Marker) -> bool:
    """Return True if any leaf of a Terraform sensitivity marker is ``true``."""
    if isinstance(marker, dict):
        return any(_is_sensitive(v) for v in marker.values())
    if isinstance(marker, list):
        return any(_is_sensitive(v) for v in marker)
    return marker is True


def _marker_for_key(marker: _Marker, key: str) -> _Marker:
    """Look up the sensitivity marker for a single top-level key.

    Terraform emits per-attribute markers as a dict, but the whole ``before_sensitive``/
    ``after_sensitive`` value may instead be a bare ``bool`` (the whole object is
    sensitive) — in that case every key inherits it rather than being looked up.
    """
    return marker.get(key) if isinstance(marker, dict) else marker


def _json_default(obj: object) -> str:
    """Serialize a ``_DisplaySentinel`` as its text so it renders inside JSON."""
    if isinstance(obj, _DisplaySentinel):
        return obj.text
    msg = f"not JSON serializable: {type(obj).__name__}"
    raise TypeError(msg)


def _resolve_marker_only(marker: _Marker) -> object:
    """Resolve a marker that has no concrete counterpart (absent or ``null`` value).

    A ``true`` leaf materializes as the known-after-apply sentinel. A dict
    marker keeps only truthy descendants, visited in sorted key order for
    deterministic output; an empty result signals absence via ``_MISSING``. A
    list marker preserves positional gaps as ``null`` up to the last meaningful
    index and drops trailing non-meaningful markers; an all-non-meaningful list
    signals absence. ``false``/``none``/other scalars signal absence.
    """
    if marker is True:
        return _KNOWN_AFTER_APPLY
    if isinstance(marker, dict):
        result: dict[str, object] = {}
        for key in sorted(marker):
            child = _resolve_marker_only(marker[key])
            if child is not _MISSING:
                result[key] = child
        return result or _MISSING
    if isinstance(marker, list):
        materialized: list[object] = []
        last_present = -1
        for item in marker:
            child = _resolve_marker_only(item)
            if child is _MISSING:
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


def _resolve_after_unknown(value: object, marker: _Marker) -> object:
    """Recursively substitute ``after_unknown`` markers into a concrete ``after`` value.

    ``value`` is ``_MISSING`` when the position has no concrete counterpart (the
    key is absent from ``after`` or explicitly ``null``, or a container marker
    extends past the concrete container). A ``true`` marker replaces the
    position with the known-after-apply sentinel. A dict marker recurses by
    key, visiting the union of the value's and marker's keys in sorted order so
    output is deterministic regardless of JSON file order; a marker-only key
    surfaces only if its subtree contains a ``true`` leaf. A list marker
    recurses by index for existing elements, then extends with a marker-only
    tail. A dict/list marker paired with a non-dict/non-list, non-null concrete
    value (shape mismatch) leaves that concrete value unchanged. Any other
    marker (``false``/``none``) keeps the concrete value, or signals absence
    via ``_MISSING`` when there is none.
    """
    if marker is True:
        return _KNOWN_AFTER_APPLY
    if marker is None or marker is False:
        return _MISSING if value is _MISSING else value
    if isinstance(marker, dict):
        return _resolve_dict_marker(value, marker)
    if isinstance(marker, list):
        return _resolve_list_marker(value, marker)
    return value


def _resolve_dict_marker(value: object, marker: dict[str, Any]) -> object:
    """Apply a dict ``after_unknown`` marker to a concrete or absent value."""
    if value is _MISSING or value is None:
        return _resolve_marker_only(marker)
    if not isinstance(value, dict):
        return value
    result: dict[str, object] = {}
    for key in sorted(set(value) | set(marker)):
        if key in value:
            child = _resolve_after_unknown(value[key], marker.get(key))
        else:
            child = _resolve_marker_only(marker[key])
        if child is not _MISSING:
            result[key] = child
    return result


def _resolve_list_marker(value: object, marker: list[Any]) -> object:
    """Apply a list ``after_unknown`` marker to a concrete or absent value."""
    if value is _MISSING or value is None:
        return _resolve_marker_only(marker)
    if not isinstance(value, list):
        return value
    resolved = [_resolve_after_unknown(item, marker[i] if i < len(marker) else None) for i, item in enumerate(value)]
    tail = marker[len(value) :]
    if tail:
        materialized_tail = _resolve_marker_only(tail)
        if isinstance(materialized_tail, list):
            resolved.extend(materialized_tail)
    return resolved


def _format_report_value(value: _ReportValue) -> str:
    r"""Format a diff value for a single Markdown resource-details table cell.

    Display sentinels (sensitive-value and known-after-apply markers) render as
    their bare human-readable text. Structured values (dicts and lists) render
    as compact, valid JSON with ``|`` escaped as ``\u007c`` and backticks as
    ``\u0060`` so the cell cannot gain a phantom table column or close its
    code-span wrapper, while the text round-trips through ``json.loads``.
    Scalar strings render as JSON-quoted strings (so a string ``"false"`` stays
    distinct from a boolean ``false`` and an empty string stays visible), with
    the same ``|`` and backtick escapes applied over the quoted text. Other
    scalars (``null``, booleans, numbers) render as their JSON literal.
    """
    if isinstance(value, _DisplaySentinel):
        return value.text
    if isinstance(value, dict | list):
        return (
            json.dumps(value, ensure_ascii=False, default=_json_default)
            .replace("|", r"\u007c")
            .replace("`", r"\u0060")
        )
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False).replace("|", r"\u007c").replace("`", r"\u0060")
    return json.dumps(value, ensure_ascii=False)


def calculate_diff(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    unknown: dict[str, Any] | None,
    before_sensitive: _Marker = None,
    after_sensitive: _Marker = None,
) -> dict[str, dict[str, Any]]:
    """Compare before/after and handle 'known after apply' values.

    Returns:
        A dict of changed attributes keyed by attribute name, in ascending lexical
        key order. The Jinja2 report template consumes this dict via ``.items()``
        and relies on that order for deterministic Markdown output — do not
        replace the sorted traversal with a hash-ordered one (e.g. iterating a
        ``set`` or unsorted ``dict`` union) without preserving the guarantee.
    """
    diff = {}
    before = before or {}
    after = after or {}
    unknown = unknown or {}

    all_keys = set(before.keys()) | set(after.keys()) | set(unknown.keys())

    for k in sorted(all_keys):
        val_before = before.get(k)
        concrete = after.get(k)
        if concrete is None:
            # Absent or explicit null: surface a marker-only unknown subtree if
            # one exists, rather than resolving against None (which would hit
            # the shape-mismatch rule and drop it).
            val_after = _resolve_after_unknown(_MISSING, unknown.get(k))
            if val_after is _MISSING:
                val_after = None
        else:
            val_after = _resolve_after_unknown(concrete, unknown.get(k))

        if val_before != val_after:
            if _is_sensitive(_marker_for_key(before_sensitive, k)) or _is_sensitive(
                _marker_for_key(after_sensitive, k)
            ):
                val_before = _SENSITIVE_VALUE
                val_after = _SENSITIVE_VALUE
            diff[k] = {"before": val_before, "after": val_after}
    return diff


def _build_type_action_row(rtype: str, counts: dict[str, int]) -> dict[str, Any]:
    """Build a type-action summary row dict for Jinja2 rendering."""
    return {
        "type": rtype,
        "count_delete": counts.get("delete", 0),
        "count_replace": counts.get("replace", 0),
        "count_update": counts.get("update", 0),
        "count_create": counts.get("create", 0),
        "total": sum(counts.values()),
    }


@app.command()
def generate(
    json_path: Path = typer.Argument(..., help="JSON plan file"),
    config_file: Path | None = typer.Option(None, "--config", "-c"),
    output_file: Path | None = typer.Option(
        None, "--output", "-o", help="Output file for markdown report (default: stdout)"
    ),
    show_sensitive: bool = typer.Option(
        False, "--show-sensitive", help="Render sensitive attribute values instead of masking them"
    ),
) -> None:
    """Generate a markdown report from a terraform plan JSON."""
    config = load_config(config_file)

    with json_path.open() as f:
        plan = TerraformPlan(**json.load(f))

    action_order = ["delete", "replace", "update", "create"]

    # Per-action, per-tier counts: tiered_summary[action][tier] = count
    tiered_summary: dict[str, dict[str, int]] = {
        action: {"critical": 0, "normal": 0, "silent": 0} for action in action_order
    }

    # Type-action counts for non-silent resources (main type table)
    type_action_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # Type-action counts for silent resources (🔇 sub-section)
    silent_type_action_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # Critical operations that land in the 🚨 section (action in critical_on)
    critical_resources_by_action: dict[str, dict[str, list[dict[str, Any]]]] = {
        action: defaultdict(list) for action in action_order
    }

    # All other visible resources (normal tier + critical ops NOT in critical_on)
    normal_resources_by_action: dict[str, dict[str, list[dict[str, Any]]]] = {
        action: defaultdict(list) for action in action_order
    }

    for rc in plan.resource_changes:
        if rc.simple_action in ("no-op", "read"):
            continue

        rule = resolve_tier(rc, config)
        action = rc.simple_action

        # Always count toward tier summary
        tiered_summary[action][rule.tier] += 1

        if rule.tier == "silent":
            silent_type_action_counts[rc.type][action] += 1
            continue

        # Non-silent: add to type table counts and compute diff
        type_action_counts[rc.type][action] += 1
        is_summarized = rule.detail == "summary"

        diff: dict[str, dict[str, str]] = {}
        if not is_summarized:
            before_sensitive = None if show_sensitive else rc.change.before_sensitive
            after_sensitive = None if show_sensitive else rc.change.after_sensitive
            raw_diff = calculate_diff(
                rc.change.before,
                rc.change.after,
                rc.change.after_unknown,
                before_sensitive,
                after_sensitive,
            )
            diff = {
                attr: {
                    "before": _format_report_value(val["before"]),
                    "after": _format_report_value(val["after"]),
                }
                for attr, val in raw_diff.items()
            }

        resource_entry: dict[str, Any] = {
            "address": rc.address,
            "short_address": f"{rc.type}.{rc.name}",
            "action": action,
            "emoji": get_emoji(action),
            "is_summarized": is_summarized,
            "diff": diff,
        }

        if rule.tier == "critical" and action in rule.critical_on:
            critical_resources_by_action[action][rc.type].append(resource_entry)
        else:
            normal_resources_by_action[action][rc.type].append(resource_entry)

    # Sort helpers — highest resource count first within each action group
    def _sort_by_type(
        by_action: dict[str, dict[str, list[dict[str, Any]]]],
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        return {
            action: dict(sorted(by_type.items(), key=lambda item: len(item[1]), reverse=True))
            for action, by_type in by_action.items()
            if by_type
        }

    critical_to_render = _sort_by_type(critical_resources_by_action)
    normal_to_render = _sort_by_type(normal_resources_by_action)

    sorted_type_action_counts = sorted(
        [_build_type_action_row(rtype, dict(counts)) for rtype, counts in type_action_counts.items()],
        key=lambda item: item["total"],
        reverse=True,
    )
    sorted_silent_type_action_counts = sorted(
        [_build_type_action_row(rtype, dict(counts)) for rtype, counts in silent_type_action_counts.items()],
        key=lambda item: item["total"],
        reverse=True,
    )

    # Jinja2 rendering
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=False,  # noqa: S701
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.md.j2")
    rendered_content = (
        template.render(
            tiered_summary=tiered_summary,
            type_action_counts=sorted_type_action_counts,
            silent_type_action_counts=sorted_silent_type_action_counts,
            critical_resources_by_action=critical_to_render,
            normal_resources_by_action=normal_to_render,
            action_order=action_order,
            get_emoji=get_emoji,
        ).rstrip()
        + "\n"
    )

    if output_file:
        if output_file.exists():
            typer.echo(f"Overwriting {output_file}")
        output_file.write_text(rendered_content)
        typer.echo(f"Report written to {output_file}")
    else:
        typer.echo(rendered_content, nl=False)


if __name__ == "__main__":
    app()
