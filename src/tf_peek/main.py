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
    mapping = {"create": "🟢", "update": "🟡", "delete": "🔴", "replace": "🔄", "no-op": "⚪"}
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
) -> None:
    """Generate a markdown report from a terraform plan JSON."""
    config = load_config(config_file)

    with json_path.open() as f:
        plan = TerraformPlan(**json.load(f))

    summary = {"create": 0, "update": 0, "delete": 0, "replace": 0}
    resources_to_render = defaultdict(list)

    for rc in plan.resource_changes:
        if rc.simple_action == "no-op" or any(rc.type.startswith(p) for p in config.ignore):
            continue

        summary[rc.simple_action] += 1
        is_summarized = any(rc.type.startswith(p) for p in config.summarize)

        diff = {}
        if not is_summarized:
            diff = calculate_diff(rc.change.before, rc.change.after, rc.change.after_unknown)

        resources_to_render[rc.module_address].append(
            {
                "address": rc.address,
                "type": rc.type,
                "action": rc.simple_action,
                "emoji": get_emoji(rc.simple_action),
                "is_summarized": is_summarized,
                "diff": diff,
            }
        )

    # Jinja2 rendering
    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True)
    template = env.get_template("report.md.j2")
    rich.print(template.render(summary=summary, resources_by_module=resources_to_render))


if __name__ == "__main__":
    app()
