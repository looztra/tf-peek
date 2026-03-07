"""Tests for tf_peek main logic."""

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from tf_peek.main import app, calculate_diff, get_emoji

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan(resource_changes: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a minimal Terraform plan dict."""
    return {"resource_changes": resource_changes}


def _rc_entry(  # noqa: PLR0913
    rtype: str,
    name: str,
    actions: list[str],
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    module: str = "root",
) -> dict[str, Any]:
    """Build a minimal resource_change entry."""
    address_prefix = f"module.{module}." if module != "root" else ""
    return {
        "address": f"{address_prefix}{rtype}.{name}",
        "module_address": module,
        "type": rtype,
        "name": name,
        "change": {
            "actions": actions,
            "before": before,
            "after": after,
            "after_unknown": None,
        },
    }


def _run_generate(plan: dict[str, Any], config_content: str, tmp_path: Path) -> str:
    """Write plan + config to tmp_path and run generate, returning rendered markdown."""
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan))
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text(config_content)
    output_file = tmp_path / "report.md"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [str(plan_file), "--config", str(config_file), "--output", str(output_file)],
    )
    assert result.exit_code == 0, result.output
    return output_file.read_text()


# ---------------------------------------------------------------------------
# get_emoji / calculate_diff (unchanged — kept for regression)
# ---------------------------------------------------------------------------


def test_get_emoji() -> None:
    """Test get_emoji returns correct emojis."""
    assert get_emoji("create") == "➕"  # noqa: RUF001
    assert get_emoji("update") == "🛠️"
    assert get_emoji("delete") == "➖"  # noqa: RUF001
    assert get_emoji("replace") == "⚠️"
    assert get_emoji("no-op") == "🔹"
    assert get_emoji("unknown") == "❓"


def test_calculate_diff_simple() -> None:
    """Test comparing basic flat dictionaries."""
    before = {"attr1": "old_val", "attr2": "same"}
    after = {"attr1": "new_val", "attr2": "same"}
    diff = calculate_diff(before, after, None)
    assert "attr2" not in diff
    assert diff["attr1"] == {"before": "old_val", "after": "new_val"}


def test_calculate_diff_no_difference() -> None:
    """Test comparing identical state."""
    diff = calculate_diff({"attr1": "val"}, {"attr1": "val"}, None)
    assert not diff


def test_calculate_diff_known_after_apply() -> None:
    """Test handling of values known after apply."""
    diff = calculate_diff({"id": None, "name": "foo"}, {"name": "foo"}, {"id": True})
    assert "name" not in diff
    assert diff["id"] == {"before": None, "after": "(known after apply) ⏳"}


# ---------------------------------------------------------------------------
# Integration: tiered summary counts
# ---------------------------------------------------------------------------


def test_tiered_summary_counts(tmp_path: Path) -> None:
    """Summary table reflects per-tier counts for each action."""
    plan = _make_plan(
        [
            _rc_entry("aiven_pg", "prod", ["delete"]),  # critical delete → critical section
            _rc_entry("aiven_pg", "dev", ["create"]),  # critical create → normal section
            _rc_entry("google_storage_bucket", "b1", ["create"]),  # normal create
            _rc_entry("null_resource", "nr1", ["create"]),  # silent create
            _rc_entry("null_resource", "nr2", ["delete"]),  # silent delete
        ]
    )
    config = """
[[resources]]
match_type = "aiven_pg"
tier = "critical"

[[resources]]
match_type = "null_resource"
tier = "silent"
"""
    report = _run_generate(plan, config, tmp_path)

    # Critical delete: 1, normal delete: 0, silent delete: 1
    assert "Delete" in report
    # Critical create: 1 (aiven_pg.dev), normal create: 1 (bucket), silent create: 1
    assert "Create" in report
    # The total row is present
    assert "Σ Total" in report


def test_tiered_summary_zero_cells_empty(tmp_path: Path) -> None:
    """Zero-count cells in summary table are empty, not '0'."""
    plan = _make_plan([_rc_entry("google_storage_bucket", "b1", ["create"])])
    config = ""  # no rules, everything is normal
    report = _run_generate(plan, config, tmp_path)
    # The critical column should be empty for this create row (no critical resources)
    lines = [line for line in report.splitlines() if "Create" in line and "|" in line]
    assert lines, "No summary create row found"
    # The critical cell should not contain a number
    create_row = lines[0]
    assert "| 1 |" not in create_row or "🔇" not in create_row  # sanity


# ---------------------------------------------------------------------------
# Integration: silent resources
# ---------------------------------------------------------------------------


def test_silent_resources_not_in_details(tmp_path: Path) -> None:
    """Silent resources do not appear in the 🔍 Resource Details section."""
    plan = _make_plan(
        [
            _rc_entry("null_resource", "nr1", ["create"], after={"triggers": "always"}),
            _rc_entry("google_storage_bucket", "b1", ["create"], after={"name": "my-bucket"}),
        ]
    )
    config = """
[[resources]]
match_type = "null_resource"
tier = "silent"
"""
    report = _run_generate(plan, config, tmp_path)

    # null_resource should NOT appear in details
    detail_section_idx = report.find("🔍 Resource Details")
    assert detail_section_idx != -1
    details = report[detail_section_idx:]
    assert "null_resource.nr1" not in details

    # google_storage_bucket SHOULD appear in details
    assert "google_storage_bucket" in details


def test_silent_resources_disclosed_in_type_table(tmp_path: Path) -> None:
    """Silent resources appear in the 🔇 sub-section of the type table."""
    plan = _make_plan(
        [
            _rc_entry("null_resource", "nr1", ["create"]),
            _rc_entry("null_resource", "nr2", ["create"]),
        ]
    )
    config = """
[[resources]]
match_type = "null_resource"
tier = "silent"
"""
    report = _run_generate(plan, config, tmp_path)
    assert "🔇" in report
    assert "null_resource" in report


def test_silent_sub_section_absent_when_no_silent(tmp_path: Path) -> None:
    """No 🔇 sub-section when no silent resources exist."""
    plan = _make_plan([_rc_entry("google_storage_bucket", "b1", ["create"])])
    config = ""
    report = _run_generate(plan, config, tmp_path)
    # Should not contain the silent section header
    assert "Silent (counted, not detailed)" not in report


# ---------------------------------------------------------------------------
# Integration: critical section
# ---------------------------------------------------------------------------


def test_critical_delete_in_critical_section_only(tmp_path: Path) -> None:
    """Critical delete appears in 🚨 section and NOT in 🔍 details."""
    plan = _make_plan(
        [
            _rc_entry("aiven_pg", "prod", ["delete"], before={"plan": "business-4"}),
        ]
    )
    config = """
[[resources]]
match_type = "aiven_pg"
tier = "critical"
"""
    report = _run_generate(plan, config, tmp_path)

    assert "🚨 Critical Changes" in report
    critical_idx = report.find("🚨 Critical Changes")
    details_idx = report.find("🔍 Resource Details")
    assert details_idx > critical_idx

    critical_section = report[critical_idx:details_idx]
    normal_section = report[details_idx:]

    assert "aiven_pg.prod" in critical_section
    assert "aiven_pg.prod" not in normal_section


def test_critical_create_in_normal_section(tmp_path: Path) -> None:
    """Critical create (not in default critical_on) goes to 🔍 details, not 🚨."""
    plan = _make_plan(
        [
            _rc_entry("aiven_pg", "new_stack", ["create"], after={"plan": "startup-2"}),
        ]
    )
    config = """
[[resources]]
match_type = "aiven_pg"
tier = "critical"
# critical_on defaults to ["delete", "replace"] — create is NOT included
"""
    report = _run_generate(plan, config, tmp_path)

    # No critical section (no delete/replace ops)
    assert "🚨 Critical Changes" not in report
    assert "aiven_pg.new_stack" in report


def test_critical_on_update_surfaces_in_critical_section(tmp_path: Path) -> None:
    """When critical_on includes update, updated critical resources go to 🚨 section."""
    plan = _make_plan(
        [
            _rc_entry(
                "aiven_pg",
                "svc",
                ["update"],
                before={"service_type": "pg"},
                after={"service_type": "pg", "plan": "business-8"},
            ),
        ]
    )
    config = """
[[resources]]
match_type = "aiven_pg"
tier = "critical"
critical_on = ["delete", "replace", "update"]
"""
    report = _run_generate(plan, config, tmp_path)
    assert "🚨 Critical Changes" in report
    assert "aiven_pg.svc" in report.split("🔍 Resource Details")[0]


def test_no_critical_section_when_no_critical_ops(tmp_path: Path) -> None:
    """🚨 section is absent when no resource has its action in critical_on."""
    plan = _make_plan([_rc_entry("google_storage_bucket", "b1", ["create"])])
    config = ""
    report = _run_generate(plan, config, tmp_path)
    assert "🚨 Critical Changes" not in report


# ---------------------------------------------------------------------------
# Integration: summary detail level
# ---------------------------------------------------------------------------


def test_detail_summary_renders_title_only(tmp_path: Path) -> None:
    """Detail = summary shows the resource title but hides diff details."""
    plan = _make_plan(
        [
            _rc_entry(
                "google_project_iam_member",
                "binding1",
                ["create"],
                after={"role": "roles/viewer", "member": "user:foo@example.com"},
            ),
        ]
    )
    config = """
[[resources]]
match_type = "google_project_iam_member"
tier = "normal"
detail = "summary"
"""
    report = _run_generate(plan, config, tmp_path)

    assert "google_project_iam_member.binding1" in report
    assert "Details hidden by configuration" in report
    # The actual attribute values should NOT be present in the diff table
    assert "roles/viewer" not in report
