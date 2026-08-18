"""Main CLI entrypoint for tf-peek."""

import json
from collections import defaultdict
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
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


# The value domain at the presentation boundary: everything the semantic diff
# tree can hold once markers are resolved. Every resolver, ``calculate_diff``
# and ``_format_report_value`` are annotated with it, so a type checker — not a
# runtime guard — is what keeps ``_Missing`` out of the formatter.
_ReportValue = str | int | float | bool | None | _DisplaySentinel | dict[str, "_ReportValue"] | list["_ReportValue"]


_KNOWN_AFTER_APPLY = _DisplaySentinel("(known after apply) ⏳")
_SENSITIVE_VALUE = _DisplaySentinel("(sensitive value)")


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
# back a plain ``_ReportValue``.
_Resolved = _ReportValue | _Missing


def _is_sensitive(marker: _Marker) -> bool:
    """Return True if any leaf of a Terraform sensitivity marker is truthy.

    Deliberately truthy rather than ``is True``: an unexpected marker shape must
    fail closed and mask the attribute rather than render a secret in plaintext.
    """
    if isinstance(marker, dict):
        return any(_is_sensitive(v) for v in marker.values())
    if isinstance(marker, list):
        return any(_is_sensitive(v) for v in marker)
    return bool(marker)


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


def _resolve_marker_only(marker: _Marker) -> _Resolved:
    """Resolve a marker for a position that has no concrete counterpart.

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
        result: dict[str, _ReportValue] = {}
        for key in sorted(marker):
            child = _resolve_marker_only(marker[key])
            if not isinstance(child, _Missing):
                result[key] = child
        return result or _MISSING
    if isinstance(marker, list):
        materialized: list[_ReportValue] = []
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


def _resolve_after_unknown(value: _ReportValue, marker: _Marker) -> _Resolved:
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
        return _KNOWN_AFTER_APPLY
    if marker is None or marker is False:
        return value
    if isinstance(marker, dict):
        return _resolve_dict_marker(value, marker)
    if isinstance(marker, list):
        return _resolve_list_marker(value, marker)
    return value


def _resolve_present(value: _ReportValue, marker: _Marker) -> _ReportValue:
    """Resolve a marker against a position the plan actually contains.

    Absence is not representable for a value that exists, so a marker carrying
    no unknown leaf retains ``value`` — including a concrete ``null``, which
    must stay visible in the rendered cell instead of being dropped. This is the
    resolver family's only narrowing from ``_Resolved`` to ``_ReportValue``,
    which is what keeps ``_MISSING`` out of the formatter.
    """
    resolved = _resolve_after_unknown(value, marker)
    return value if isinstance(resolved, _Missing) else resolved


def _resolve_dict_marker(value: _ReportValue, marker: dict[str, Any]) -> _Resolved:
    """Apply a dict ``after_unknown`` marker to a concrete value."""
    if value is None:
        return _resolve_marker_only(marker)
    if not isinstance(value, dict):
        return value
    # Concrete keys keep the plan's order so both cells of a row stay
    # comparable; marker-only keys are appended in sorted order, the only place
    # this transformation invents an ordering.
    result: dict[str, _ReportValue] = {key: _resolve_present(child, marker.get(key)) for key, child in value.items()}
    for key in sorted(set(marker) - set(value)):
        extra = _resolve_marker_only(marker[key])
        if not isinstance(extra, _Missing):
            result[key] = extra
    return result


def _resolve_list_marker(value: _ReportValue, marker: list[Any]) -> _Resolved:
    """Apply a list ``after_unknown`` marker to a concrete value."""
    if value is None:
        return _resolve_marker_only(marker)
    if not isinstance(value, list):
        return value
    resolved: list[_ReportValue] = [
        _resolve_present(item, marker[i] if i < len(marker) else None) for i, item in enumerate(value)
    ]
    tail = _resolve_marker_only(marker[len(value) :])
    if isinstance(tail, list):
        resolved.extend(tail)
    return resolved


def _format_report_value(value: _ReportValue) -> str:
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
    if isinstance(value, _DisplaySentinel):
        return value.text
    return json.dumps(value, ensure_ascii=False, default=_json_default).replace("|", r"\u007c").replace("`", r"\u0060")


def calculate_diff(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    unknown: _Marker = None,
    before_sensitive: _Marker = None,
    after_sensitive: _Marker = None,
) -> dict[str, dict[str, _ReportValue]]:
    """Compare before/after and handle 'known after apply' values.

    Returns:
        A dict of changed attributes keyed by attribute name, in ascending lexical
        key order. The Jinja2 report template consumes this dict via ``.items()``
        and relies on that order for deterministic Markdown output — do not
        replace the sorted traversal with a hash-ordered one (e.g. iterating a
        ``set`` or unsorted ``dict`` union) without preserving the guarantee.
    """
    diff: dict[str, dict[str, _ReportValue]] = {}
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
        val_before: _ReportValue = before.get(k)
        marker = unknown_map.get(k)
        if k in after:
            val_after = _resolve_present(after[k], marker)
        else:
            # No concrete counterpart: surface a marker-only unknown subtree if
            # one exists, otherwise report the attribute as absent.
            resolved = _resolve_marker_only(marker)
            val_after = None if isinstance(resolved, _Missing) else resolved

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


def _version_callback(ctx: typer.Context, show_version: bool) -> None:
    """Print the installed tf-peek version and exit, if the flag was passed.

    Registered as an eager typer callback so it runs — and can exit — before
    the required ``json_path`` argument is validated, matching the standard
    click/typer ``--version`` pattern.
    """
    if ctx.resilient_parsing:
        return
    if show_version:
        try:
            typer.echo(_package_version("tf-peek"))
        except PackageNotFoundError:
            typer.echo("tf-peek version unknown (package metadata not found)")
        raise typer.Exit


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
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed tf-peek version and exit.",
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
        # Pin the encoding and line ending: click already forces UTF-8 with LF on
        # stdout, so both destinations must agree byte-for-byte regardless of the
        # ambient locale (an ASCII default would otherwise abort on the report's
        # emoji, and a Windows default would rewrite every newline).
        output_file.write_text(rendered_content, encoding="utf-8", newline="\n")
        typer.echo(f"Report written to {output_file}")
    else:
        # ``color=True`` stops click from stripping ANSI escapes when stdout is
        # not a TTY, so report content reaches stdout byte-identically to the
        # ``--output`` file.
        typer.echo(rendered_content, nl=False, color=True)


if __name__ == "__main__":
    app()
