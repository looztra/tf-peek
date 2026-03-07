"""Main CLI entrypoint for tf-peek."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import rich
import typer
from jinja2 import Environment, FileSystemLoader

from .config import load_config, resolve_tier
from .models import TerraformPlan

app = typer.Typer()


def get_emoji(action: str) -> str:
    """Return an emoji representation of a terraform action."""
    mapping = {"create": "➕", "update": "🛠️", "delete": "➖", "replace": "⚠️", "no-op": "🔹"}  # noqa: RUF001
    return mapping.get(action, "❓")


def calculate_diff(
    before: dict[str, Any] | None, after: dict[str, Any] | None, unknown: dict[str, Any] | None
) -> dict[str, dict[str, Any]]:
    """Compare before/after and handle 'known after apply' values."""
    diff = {}
    before = before or {}
    after = after or {}
    unknown = unknown or {}

    all_keys = set(before.keys()) | set(after.keys()) | set(unknown.keys())

    for k in all_keys:
        val_before = before.get(k)
        val_after = after.get(k)

        # If the value is marked as unknown in the plan
        if k in unknown and unknown[k] is True:
            val_after = "(known after apply) ⏳"

        if val_before != val_after:
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
            diff = calculate_diff(rc.change.before, rc.change.after, rc.change.after_unknown)

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
    rendered_content = template.render(
        tiered_summary=tiered_summary,
        type_action_counts=sorted_type_action_counts,
        silent_type_action_counts=sorted_silent_type_action_counts,
        critical_resources_by_action=critical_to_render,
        normal_resources_by_action=normal_to_render,
        action_order=action_order,
        get_emoji=get_emoji,
    )

    if output_file:
        if output_file.exists():
            typer.echo(f"Overwriting {output_file}")
        output_file.write_text(rendered_content)
        typer.echo(f"Report written to {output_file}")
    else:
        rich.print(rendered_content)


if __name__ == "__main__":
    app()
