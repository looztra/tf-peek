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


def _is_sensitive(marker: bool | dict[str, Any] | list[Any] | None) -> bool:
    """Return True if any leaf of a Terraform sensitivity marker is truthy."""
    if isinstance(marker, dict):
        return any(_is_sensitive(v) for v in marker.values())
    if isinstance(marker, list):
        return any(_is_sensitive(v) for v in marker)
    return bool(marker)


def _marker_for_key(
    marker: bool | dict[str, Any] | list[Any] | None, key: str
) -> bool | dict[str, Any] | list[Any] | None:
    """Look up the sensitivity marker for a single top-level key.

    Terraform emits per-attribute markers as a dict, but the whole `before_sensitive`/
    `after_sensitive` value may instead be a bare `bool` (the whole object is sensitive) —
    in that case every key inherits it rather than being looked up.
    """
    return marker.get(key) if isinstance(marker, dict) else marker


_KNOWN_AFTER_APPLY = "(known after apply) ⏳"
_SENSITIVE_VALUE = "(sensitive value)"

_JSONValue = str | int | float | bool | dict[str, "_JSONValue"] | list["_JSONValue"] | None


def _materialize_unknown_marker(
    marker: bool | dict[str, Any] | list[Any] | None,
) -> tuple[bool, _JSONValue]:
    """Materialize a marker-only `after_unknown` subtree with no concrete counterpart.

    Used when an `after_unknown` marker has no matching concrete `after` value —
    either the top-level attribute is absent from `after`, or a dict/list marker
    extends past the concrete container's keys/length. Returns a `(present, value)`
    pair: `present` is `True` only when the marker contains at least one truthy
    leaf, so callers can omit branches that carry no meaningful unknown value.

    A `True` leaf materializes as the known-after-apply sentinel. `False`, `None`,
    and any other non-container scalar are never meaningful, matching the literal-
    `True` semantics `_resolve_after_unknown` already uses for leaf markers. A dict
    marker keeps only truthy descendants, visited in sorted key order for
    deterministic output. A list marker keeps the prefix through the last truthy
    index, using `None` for intervening non-meaningful positions so a later
    meaningful index does not shift; non-meaningful trailing entries are dropped.
    """
    if marker is True:
        return True, _KNOWN_AFTER_APPLY
    if isinstance(marker, dict):
        materialized_dict: dict[str, _JSONValue] = {}
        for key in sorted(marker):
            present, value = _materialize_unknown_marker(marker[key])
            if present:
                materialized_dict[key] = value
        return (True, materialized_dict) if materialized_dict else (False, None)
    if isinstance(marker, list):
        materialized_list: list[_JSONValue] = []
        last_present_index = -1
        for item in marker:
            present, value = _materialize_unknown_marker(item)
            materialized_list.append(value if present else None)
            if present:
                last_present_index = len(materialized_list) - 1
        if last_present_index < 0:
            return False, None
        return True, materialized_list[: last_present_index + 1]
    return False, None


def _resolve_after_unknown(value: _JSONValue, marker: bool | dict[str, Any] | list[Any] | None) -> _JSONValue:
    """Recursively substitute `after_unknown` markers into a concrete `after` value.

    A truthy marker replaces the value at that position with the known-after-apply
    display sentinel. Object markers recurse by key, including keys that exist only
    in the marker via `_materialize_unknown_marker` (so unknown-only properties are
    not omitted, but non-meaningful marker-only branches — `False`, `None`, or a
    branch with no truthy descendant — are omitted rather than surfacing as JSON
    `null`); marker-only keys are visited in sorted order to keep output
    deterministic. List markers recurse by index for existing elements, then
    extend with a marker-only tail materialized by `_materialize_unknown_marker`,
    which preserves positional gaps (as JSON `null`) up to the last meaningful
    trailing marker and drops non-meaningful markers after it. Any other marker
    shape (`False`, `None`, or a marker that does not match the value's shape)
    leaves the value unchanged.
    """
    if marker is True:
        return _KNOWN_AFTER_APPLY
    if isinstance(marker, dict):
        if not isinstance(value, dict):
            return value
        result = {key: _resolve_after_unknown(val, marker.get(key)) for key, val in value.items()}
        for key in sorted(marker):
            if key not in result:
                present, materialized = _materialize_unknown_marker(marker[key])
                if present:
                    result[key] = materialized
        return result
    if isinstance(marker, list):
        if not isinstance(value, list):
            return value
        result_list = [
            _resolve_after_unknown(item, marker[i] if i < len(marker) else None) for i, item in enumerate(value)
        ]
        present, tail = _materialize_unknown_marker(marker[len(value) :])
        if present:
            assert isinstance(tail, list)  # noqa: S101 — guaranteed by the list-marker branch above
            result_list.extend(tail)
        return result_list
    return value


def _format_report_value(value: _JSONValue) -> str:
    r"""Format a diff value for a single Markdown resource-details table cell.

    Structured values (dicts and lists) render as compact, valid JSON. A
    literal `|` is replaced with the JSON escape sequence `\\u007c` — not the
    GFM backslash form — so the cell cannot gain a phantom table column while
    the text remains valid JSON that round-trips through `json.loads`.
    Physical line breaks inside a JSON string are already valid JSON escapes,
    so structured values receive no separate newline normalization.

    Scalar strings — including the `(sensitive value)` and `(known after
    apply) ⏳` display sentinels — are not JSON documents, so they normalize
    line endings into visible `\\n` notation and escape literal `|` with the
    GFM table-cell backslash form instead.

    Other scalars (`null`, booleans, numbers) render as their JSON literal.
    """
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False).replace("|", r"\u007c")
    if isinstance(value, str):
        text = value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
        return text.replace("|", r"\|")
    return json.dumps(value, ensure_ascii=False)


def calculate_diff(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    unknown: dict[str, Any] | None,
    before_sensitive: bool | dict[str, Any] | list[Any] | None = None,
    after_sensitive: bool | dict[str, Any] | list[Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Compare before/after and handle 'known after apply' values.

    Returns:
        A dict of changed attributes keyed by attribute name, in ascending lexical
        key order. The Jinja2 report template consumes this dict via `.items()`
        and relies on that order for deterministic Markdown output — do not
        replace the sorted traversal with a hash-ordered one (e.g. iterating a
        `set` or unsorted `dict` union) without preserving the guarantee.
    """
    diff = {}
    before = before or {}
    after = after or {}
    unknown = unknown or {}

    all_keys = set(before.keys()) | set(after.keys()) | set(unknown.keys())

    for k in sorted(all_keys):
        val_before = before.get(k)

        if k in after:
            # Recursively substitute nested `after_unknown` markers into the after value
            val_after = _resolve_after_unknown(after[k], unknown.get(k))
        else:
            # No concrete after value: surface a marker-only unknown subtree if one
            # exists, rather than resolving against an absent `None` value (which
            # would trigger the shape-mismatch rule and drop it).
            present, val_after = _materialize_unknown_marker(unknown.get(k))
            if not present:
                val_after = None

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

        diff = {}
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
