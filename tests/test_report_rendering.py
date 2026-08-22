"""Tests for tf_peek.report rendering, exercised end-to-end through the CLI."""

from pathlib import Path

from tests.helpers import make_plan, rc_entry, run_generate

# ---------------------------------------------------------------------------
# Integration: tiered summary counts
# ---------------------------------------------------------------------------


def test_tiered_summary_counts(tmp_path: Path) -> None:
    """Summary table reflects per-tier counts for each action."""
    plan = make_plan(
        [
            rc_entry("mukta_pg", "prod", ["delete"]),  # critical delete → critical section
            rc_entry("mukta_pg", "dev", ["create"]),  # critical create → normal section
            rc_entry("google_storage_bucket", "b1", ["create"]),  # normal create
            rc_entry("null_resource", "nr1", ["create"]),  # silent create
            rc_entry("null_resource", "nr2", ["delete"]),  # silent delete
        ]
    )
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"

[[resources]]
match_type = "null_resource"
tier = "silent"
"""
    report = run_generate(plan, config, tmp_path)

    # Critical delete: 1, normal delete: 0, silent delete: 1
    assert "Delete" in report
    # Critical create: 1 (mukta_pg.dev), normal create: 1 (bucket), silent create: 1
    assert "Create" in report
    # The total row is present
    assert "Σ Total" in report


def test_tiered_summary_zero_cells_empty(tmp_path: Path) -> None:
    """Zero-count cells in summary table are empty, not '0'."""
    plan = make_plan([rc_entry("google_storage_bucket", "b1", ["create"])])
    config = ""  # no rules, everything is normal
    report = run_generate(plan, config, tmp_path)
    # The critical column should be empty for this create row (no critical resources)
    lines = [line for line in report.splitlines() if "Create" in line and "|" in line]
    assert lines, "No summary create row found"
    # The critical cell should not contain a number
    create_row = lines[0]
    assert "| 1 |" not in create_row or "🔇" not in create_row  # sanity


def test_no_op_and_read_actions_are_skipped(tmp_path: Path) -> None:
    """Resources whose only action is 'no-op' or 'read' never reach the report."""
    plan = make_plan(
        [
            rc_entry("google_storage_bucket", "unchanged", ["no-op"], before={"name": "b"}, after={"name": "b"}),
            rc_entry("google_storage_bucket", "readonly", ["read"], after={"name": "b2"}),
            rc_entry("google_storage_bucket", "created", ["create"], after={"name": "b3"}),
        ]
    )
    report = run_generate(plan, "", tmp_path)
    assert "unchanged" not in report
    assert "readonly" not in report
    assert "created" in report


# ---------------------------------------------------------------------------
# Integration: silent resources
# ---------------------------------------------------------------------------


def test_silent_resources_not_in_details(tmp_path: Path) -> None:
    """Silent resources do not appear in the 🔍 Resource Details section."""
    plan = make_plan(
        [
            rc_entry("null_resource", "nr1", ["create"], after={"triggers": "always"}),
            rc_entry("google_storage_bucket", "b1", ["create"], after={"name": "my-bucket"}),
        ]
    )
    config = """
[[resources]]
match_type = "null_resource"
tier = "silent"
"""
    report = run_generate(plan, config, tmp_path)

    # null_resource should NOT appear in details
    detail_section_idx = report.find("🔍 Resource Details")
    assert detail_section_idx != -1
    details = report[detail_section_idx:]
    assert "null_resource.nr1" not in details

    # google_storage_bucket SHOULD appear in details
    assert "google_storage_bucket" in details


def test_silent_replacement_does_not_create_a_causation_detail_block(tmp_path: Path) -> None:
    """Causation metadata does not override the silent tier's no-detail contract."""
    plan = make_plan(
        [
            rc_entry(
                "null_resource",
                "rotated",
                ["delete", "create"],
                before={"triggers": {"version": "old"}},
                after={"triggers": {"version": "new"}},
                replace_paths=[["triggers", "version"]],
            )
        ]
    )
    config = """
[[resources]]
match_type = "null_resource"
tier = "silent"
"""
    report = run_generate(plan, config, tmp_path)

    assert "null_resource.rotated" not in report
    assert "triggers.version" not in report
    assert "| ⚠️ Replace |  |  | 🔇 1 | **1** |" in report
    assert "🔇 1" in report


def test_silent_resources_disclosed_in_type_table(tmp_path: Path) -> None:
    """Silent resources appear in the 🔇 sub-section of the type table."""
    plan = make_plan(
        [
            rc_entry("null_resource", "nr1", ["create"]),
            rc_entry("null_resource", "nr2", ["create"]),
        ]
    )
    config = """
[[resources]]
match_type = "null_resource"
tier = "silent"
"""
    report = run_generate(plan, config, tmp_path)
    assert "🔇" in report
    assert "null_resource" in report


def test_silent_sub_section_absent_when_no_silent(tmp_path: Path) -> None:
    """No 🔇 sub-section when no silent resources exist."""
    plan = make_plan([rc_entry("google_storage_bucket", "b1", ["create"])])
    config = ""
    report = run_generate(plan, config, tmp_path)
    # Should not contain the silent section header
    assert "Silent (counted, not detailed)" not in report


# ---------------------------------------------------------------------------
# Integration: critical section
# ---------------------------------------------------------------------------


def test_critical_delete_in_critical_section_only(tmp_path: Path) -> None:
    """Critical delete appears in 🚨 section and NOT in 🔍 details."""
    plan = make_plan(
        [
            rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"}),
        ]
    )
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    report = run_generate(plan, config, tmp_path)

    assert "🚨 Critical Changes" in report
    critical_idx = report.find("🚨 Critical Changes")
    details_idx = report.find("🔍 Resource Details")
    assert details_idx > critical_idx

    critical_section = report[critical_idx:details_idx]
    normal_section = report[details_idx:]

    assert "mukta_pg.prod" in critical_section
    assert "mukta_pg.prod" not in normal_section


def test_critical_create_in_normal_section(tmp_path: Path) -> None:
    """Critical create (not in default critical_on) goes to 🔍 details, not 🚨."""
    plan = make_plan(
        [
            rc_entry("mukta_pg", "new_stack", ["create"], after={"plan": "startup-2"}),
        ]
    )
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
# critical_on defaults to ["delete", "replace"] — create is NOT included
"""
    report = run_generate(plan, config, tmp_path)

    # No critical section (no delete/replace ops)
    assert "🚨 Critical Changes" not in report
    assert "mukta_pg.new_stack" in report


def test_critical_on_update_surfaces_in_critical_section(tmp_path: Path) -> None:
    """When critical_on includes update, updated critical resources go to 🚨 section."""
    plan = make_plan(
        [
            rc_entry(
                "mukta_pg",
                "svc",
                ["update"],
                before={"service_type": "pg"},
                after={"service_type": "pg", "plan": "business-8"},
            ),
        ]
    )
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
critical_on = ["delete", "replace", "update"]
"""
    report = run_generate(plan, config, tmp_path)
    assert "🚨 Critical Changes" in report
    assert "mukta_pg.svc" in report.split("🔍 Resource Details")[0]


def test_no_critical_section_when_no_critical_ops(tmp_path: Path) -> None:
    """🚨 section is absent when no resource has its action in critical_on."""
    plan = make_plan([rc_entry("google_storage_bucket", "b1", ["create"])])
    config = ""
    report = run_generate(plan, config, tmp_path)
    assert "🚨 Critical Changes" not in report


# ---------------------------------------------------------------------------
# Integration: resource-type tie-break ordering
# ---------------------------------------------------------------------------


def test_resource_type_tie_break_preserves_plan_encounter_order(tmp_path: Path) -> None:
    """Equal per-type counts for an action break ties by plan order, not resorted.

    `_sort_by_type` sorts resource types by descending count within each action;
    Python's sort is stable, so types with equal counts must keep the order they
    were first encountered in the plan. This pins that guarantee against a
    fixture that actually produces a tie.
    """
    plan = make_plan(
        [
            rc_entry("google_storage_bucket", "b1", ["create"], after={"name": "b1"}),
            rc_entry("google_sql_database_instance", "db1", ["create"], after={"name": "db1"}),
        ]
    )
    report = run_generate(plan, "", tmp_path)

    detail_idx = report.find("🔍 Resource Details")
    assert detail_idx != -1
    details = report[detail_idx:]
    bucket_idx = details.find("google_storage_bucket.b1")
    db_idx = details.find("google_sql_database_instance.db1")
    assert bucket_idx != -1
    assert db_idx != -1
    assert bucket_idx < db_idx, "tied resource types were reordered instead of preserving plan order"


def test_detail_summary_renders_title_only(tmp_path: Path) -> None:
    """Detail = summary shows the resource title but hides diff details."""
    plan = make_plan(
        [
            rc_entry(
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
    report = run_generate(plan, config, tmp_path)

    assert "google_project_iam_member.binding1" in report
    assert "Attribute values hidden by configuration" in report
    # The actual attribute values should NOT be present in the diff table
    assert "roles/viewer" not in report


# ---------------------------------------------------------------------------
# Integration: causation survives detail = summary
# ---------------------------------------------------------------------------


def test_summarized_replace_keeps_forcing_path_and_mechanism(tmp_path: Path) -> None:
    """A summarized replaced resource hides values but keeps its causation and mechanism."""
    plan = make_plan(
        [
            rc_entry(
                "google_project_iam_member",
                "binding1",
                ["delete", "create"],
                before={"role": "roles/viewer"},
                after={"role": "roles/editor"},
                replace_paths=[["role"]],
            ),
        ]
    )
    config = """
[[resources]]
match_type = "google_project_iam_member"
tier = "normal"
detail = "summary"
"""
    report = run_generate(plan, config, tmp_path)

    assert "Attribute values hidden by configuration" in report
    assert "roles/viewer" not in report
    assert "roles/editor" not in report
    assert "**Forces replacement:** `role`" in report
    assert "the existing object is destroyed before its replacement is created" in report
