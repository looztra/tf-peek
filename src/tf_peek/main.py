"""Main CLI entrypoint for tf-peek."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import rich
import typer
from jinja2 import Environment, FileSystemLoader

from .config import load_config
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
    summary: dict[str, int] = {"create": 0, "update": 0, "delete": 0, "replace": 0}
    type_action_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    resources_by_action: dict[str, dict[str, list[dict[str, Any]]]] = {
        action: defaultdict(list) for action in action_order
    }

    for rc in plan.resource_changes:
        if rc.simple_action in ("no-op", "read") or any(rc.type.startswith(p) for p in config.ignore):
            continue

        summary[rc.simple_action] += 1
        type_action_counts[rc.type][rc.simple_action] += 1
        is_summarized = any(rc.type.startswith(p) for p in config.summarize)

        diff = {}
        if not is_summarized:
            diff = calculate_diff(rc.change.before, rc.change.after, rc.change.after_unknown)

        resources_by_action[rc.simple_action][rc.type].append(
            {
                "address": rc.address,
                "action": rc.simple_action,
                "emoji": get_emoji(rc.simple_action),
                "is_summarized": is_summarized,
                "diff": diff,
            }
        )

    # Sort types alphabetically within each action
    resources_to_render = {
        action: dict(sorted(by_type.items())) for action, by_type in resources_by_action.items() if by_type
    }
    # Sort types alphabetically and convert to list of dicts with action counts
    # Use prefixed keys to avoid conflicts with dict methods
    sorted_type_action_counts = [
        {
            "type": rtype,
            "count_delete": dict(counts).get("delete", 0),
            "count_replace": dict(counts).get("replace", 0),
            "count_update": dict(counts).get("update", 0),
            "count_create": dict(counts).get("create", 0),
            "total": sum(counts.values()),
        }
        for rtype, counts in sorted(type_action_counts.items())
    ]

    # Jinja2 rendering
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=False,  # noqa: S701
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.md.j2")
    rendered_content = template.render(
        summary=summary,
        type_action_counts=sorted_type_action_counts,
        resources_by_action=resources_to_render,
        action_order=[a for a in action_order if a in resources_to_render],
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
