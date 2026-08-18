"""Aggregation of a Terraform plan into report data, and Markdown template rendering."""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from .actions import ACTION_ORDER, get_emoji
from .config import PeekConfig, resolve_tier
from .diff import calculate_diff
from .formatting import format_report_value
from .models import TerraformPlan


@dataclass(frozen=True, slots=True)
class ReportData:
    """Everything the report template and the exit-code gate need."""

    tiered_summary: dict[str, dict[str, int]]
    type_action_counts: list[dict[str, Any]]
    silent_type_action_counts: list[dict[str, Any]]
    critical_resources_by_action: dict[str, dict[str, list[dict[str, Any]]]]
    normal_resources_by_action: dict[str, dict[str, list[dict[str, Any]]]]


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


def _sort_by_type(
    by_action: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Sort resource types within each action group — highest resource count first."""
    return {
        action: dict(sorted(by_type.items(), key=lambda item: len(item[1]), reverse=True))
        for action, by_type in by_action.items()
        if by_type
    }


def build_report_data(plan: TerraformPlan, config: PeekConfig, *, show_sensitive: bool) -> ReportData:
    """Classify, diff and aggregate a plan's resource changes into report data."""
    action_order = ACTION_ORDER

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
                    "before": format_report_value(val["before"]),
                    "after": format_report_value(val["after"]),
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

    return ReportData(
        tiered_summary=tiered_summary,
        type_action_counts=sorted_type_action_counts,
        silent_type_action_counts=sorted_silent_type_action_counts,
        critical_resources_by_action=_sort_by_type(critical_resources_by_action),
        normal_resources_by_action=_sort_by_type(normal_resources_by_action),
    )


def render_report(data: ReportData) -> str:
    """Render a ``ReportData`` through the Jinja2 Markdown template."""
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=False,  # noqa: S701
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.md.j2")
    return (
        template.render(
            tiered_summary=data.tiered_summary,
            type_action_counts=data.type_action_counts,
            silent_type_action_counts=data.silent_type_action_counts,
            critical_resources_by_action=data.critical_resources_by_action,
            normal_resources_by_action=data.normal_resources_by_action,
            action_order=ACTION_ORDER,
            get_emoji=get_emoji,
        ).rstrip()
        + "\n"
    )
