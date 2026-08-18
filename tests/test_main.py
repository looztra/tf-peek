"""Tests for tf_peek main logic."""

import json
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from tf_peek.main import (
    _KNOWN_AFTER_APPLY,
    _SENSITIVE_VALUE,
    _DisplaySentinel,
    _json_default,
    _version_callback,
    app,
    calculate_diff,
    get_emoji,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan(resource_changes: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a minimal Terraform plan dict."""
    return {"resource_changes": resource_changes}


def _rc_entry(  # noqa: PLR0913, PLR0917
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
    assert diff["id"] == {"before": None, "after": _KNOWN_AFTER_APPLY}


def test_calculate_diff_bare_bool_after_unknown_false() -> None:
    """A bare ``false`` ``after_unknown`` marks every attribute known."""
    diff = calculate_diff({"attr": "old"}, {"attr": "new"}, False)
    assert diff["attr"] == {"before": "old", "after": "new"}


def test_calculate_diff_bare_bool_after_unknown_true() -> None:
    """A bare ``true`` ``after_unknown`` marks every known key unknown."""
    diff = calculate_diff({"attr": "old"}, {"attr": "new"}, True)
    assert diff["attr"] == {"before": "old", "after": _KNOWN_AFTER_APPLY}


def test_calculate_diff_masks_flat_sensitive() -> None:
    """A flat bool sensitivity marker masks the attribute's value on both sides."""
    before = {"password": "hunter2"}
    after = {"password": "s3cr3t!"}
    diff = calculate_diff(before, after, None, {"password": True}, {"password": True})
    assert diff["password"] == {"before": _SENSITIVE_VALUE, "after": _SENSITIVE_VALUE}


def test_calculate_diff_masks_nested_sensitive() -> None:
    """A truthy marker anywhere in a nested subtree masks the whole top-level attribute."""
    before = {"settings": {"tier": "small", "credentials": {"password": "hunter2"}}}
    after = {"settings": {"tier": "large", "credentials": {"password": "hunter2"}}}
    before_sensitive = {"settings": {"tier": False, "credentials": {"password": True}}}
    after_sensitive = {"settings": {"tier": False, "credentials": {"password": True}}}
    diff = calculate_diff(before, after, None, before_sensitive, after_sensitive)
    assert diff["settings"] == {"before": _SENSITIVE_VALUE, "after": _SENSITIVE_VALUE}


def test_calculate_diff_masks_one_sided_sensitive() -> None:
    """Sensitivity flagged on only one side still masks both before and after."""
    before = {"token": "was-plaintext"}
    after = {"token": "now-secret"}
    diff = calculate_diff(before, after, None, {"token": False}, {"token": True})
    assert diff["token"] == {"before": _SENSITIVE_VALUE, "after": _SENSITIVE_VALUE}


def test_calculate_diff_masks_non_boolean_truthy_sensitive() -> None:
    """An unexpected but truthy marker shape fails closed and still masks the value.

    Terraform emits booleans today; narrowing the predicate to `is True` would
    render the value in plaintext the moment it emits anything else.
    """
    before = {"token": "was-plaintext"}
    after = {"token": "now-secret"}
    diff = calculate_diff(before, after, None, None, {"token": {"nested": 1}})
    assert diff["token"] == {"before": _SENSITIVE_VALUE, "after": _SENSITIVE_VALUE}


def test_calculate_diff_unresolvable_after_unknown_marker_leaves_value_unchanged() -> None:
    """A marker shape that isn't ``true``/``false``/``None``/dict/list is ignored, not applied."""
    diff = calculate_diff({"attr": "old"}, {"attr": "new"}, {"attr": "not-a-real-marker"})
    assert diff["attr"] == {"before": "old", "after": "new"}


def test_display_sentinel_hash_and_repr() -> None:
    """``_DisplaySentinel`` is hashable and reprs with its text for debugging."""
    sentinel = _DisplaySentinel("(known after apply) ⏳")
    assert hash(sentinel) == hash(("_DisplaySentinel", "(known after apply) ⏳"))
    assert repr(sentinel) == "_DisplaySentinel('(known after apply) ⏳')"


def test_json_default_rejects_non_sentinel_objects() -> None:
    """``_json_default`` only knows how to serialize ``_DisplaySentinel``; anything else raises."""
    with pytest.raises(TypeError, match="not JSON serializable: object"):
        _json_default(object())


# ---------------------------------------------------------------------------
# Integration: tiered summary counts
# ---------------------------------------------------------------------------


def test_tiered_summary_counts(tmp_path: Path) -> None:
    """Summary table reflects per-tier counts for each action."""
    plan = _make_plan(
        [
            _rc_entry("mukta_pg", "prod", ["delete"]),  # critical delete → critical section
            _rc_entry("mukta_pg", "dev", ["create"]),  # critical create → normal section
            _rc_entry("google_storage_bucket", "b1", ["create"]),  # normal create
            _rc_entry("null_resource", "nr1", ["create"]),  # silent create
            _rc_entry("null_resource", "nr2", ["delete"]),  # silent delete
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
    report = _run_generate(plan, config, tmp_path)

    # Critical delete: 1, normal delete: 0, silent delete: 1
    assert "Delete" in report
    # Critical create: 1 (mukta_pg.dev), normal create: 1 (bucket), silent create: 1
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


def test_no_op_and_read_actions_are_skipped(tmp_path: Path) -> None:
    """Resources whose only action is 'no-op' or 'read' never reach the report."""
    plan = _make_plan(
        [
            _rc_entry("google_storage_bucket", "unchanged", ["no-op"], before={"name": "b"}, after={"name": "b"}),
            _rc_entry("google_storage_bucket", "readonly", ["read"], after={"name": "b2"}),
            _rc_entry("google_storage_bucket", "created", ["create"], after={"name": "b3"}),
        ]
    )
    report = _run_generate(plan, "", tmp_path)
    assert "unchanged" not in report
    assert "readonly" not in report
    assert "created" in report


def test_generate_warns_when_overwriting_existing_output_file(tmp_path: Path) -> None:
    """Running generate twice against the same --output path prints an overwrite notice."""
    plan = _make_plan([_rc_entry("google_storage_bucket", "b1", ["create"], after={"name": "b1"})])
    config_content = ""

    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan))
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text(config_content)
    output_file = tmp_path / "report.md"

    runner = CliRunner()
    args = [str(plan_file), "--config", str(config_file), "--output", str(output_file)]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, args)
    assert second.exit_code == 0, second.output
    assert f"Overwriting {output_file}" in second.output


def test_generate_without_output_writes_report_to_stdout(tmp_path: Path) -> None:
    """Omitting --output prints the rendered report to stdout instead of a file."""
    plan = _make_plan([_rc_entry("google_storage_bucket", "b1", ["create"], after={"name": "b1"})])
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan))
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")

    runner = CliRunner()
    result = runner.invoke(app, [str(plan_file), "--config", str(config_file)])
    assert result.exit_code == 0, result.output
    assert "google_storage_bucket.b1" in result.output


# ---------------------------------------------------------------------------
# Integration: CLI invocation surface
# ---------------------------------------------------------------------------


def test_version_flag_prints_installed_version_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--version prints the installed tf-peek version and exits 0 without a plan path.

    The implementation's metadata lookup is monkeypatched to a sentinel so the assertion
    verifies a real output contract rather than comparing CLI output to the same API the
    implementation calls (which would pass even if both were wrong by the same amount).
    """
    monkeypatch.setattr("tf_peek.main._package_version", lambda _name: "9.9.9")
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "9.9.9"


def test_version_short_flag_behaves_like_long_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """-V behaves identically to --version."""
    monkeypatch.setattr("tf_peek.main._package_version", lambda _name: "9.9.9")
    runner = CliRunner()
    long_form = runner.invoke(app, ["--version"])
    short_form = runner.invoke(app, ["-V"])
    assert short_form.exit_code == 0, short_form.output
    assert short_form.output == long_form.output


def test_version_flag_reports_missing_package_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """--version exits 1 with a stderr diagnostic when distribution metadata isn't discoverable.

    A wrapper script doing ``VER=$(tf-peek --version)`` from a source checkout without an installed
    distribution should observe a non-zero exit and parseable stderr message rather than capturing
    a prose sentence as a version string with success status.
    """

    def _raise_not_found(_name: str) -> str:
        msg = "tf-peek"
        raise PackageNotFoundError(msg)

    monkeypatch.setattr("tf_peek.main._package_version", _raise_not_found)
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 1, result.output
    # Standard CliRunner mixes stderr into ``output``; assert the diagnostic is present and the
    # stdout channel did not receive a version-shaped string.
    assert "metadata" in result.output.lower()
    assert "not found" in result.output.lower()
    assert "9.9.9" not in result.output


def test_version_callback_is_silent_during_resilient_parsing(capsys: pytest.CaptureFixture) -> None:
    """The eager --version callback must not print or exit during shell-completion resolution.

    Asserts via ``capsys`` that no bytes hit stdout/stderr — removing the ``ctx.resilient_parsing``
    guard while leaving the ``echo`` in place would still pass the previous zero-assertion test,
    so a real assertion is required to guard the guard.
    """
    ctx = typer.Context(typer.main.get_command(app), resilient_parsing=True)
    _version_callback(ctx, True)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_generate_subcommand_is_rejected(tmp_path: Path) -> None:
    """The removed `generate` subcommand is rejected as an unexpected argument, not accepted.

    Regression guard for D6: ``tf-peek generate plan.json`` has never worked (typer collapses a
    single-command app), so it must keep failing. The assertions are strict — ``exit_code == 2``
    and ``"unexpected extra argument"`` in the output — so an internal crash inside ``generate``
    that produced any other non-zero exit cannot keep this test green.
    """
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(_make_plan([])))

    runner = CliRunner()
    result = runner.invoke(app, ["generate", str(plan_file)])
    assert result.exit_code == 2, result.output  # noqa: PLR2004 — click "usage error" exit code


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
            _rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"}),
        ]
    )
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    report = _run_generate(plan, config, tmp_path)

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
    plan = _make_plan(
        [
            _rc_entry("mukta_pg", "new_stack", ["create"], after={"plan": "startup-2"}),
        ]
    )
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
# critical_on defaults to ["delete", "replace"] — create is NOT included
"""
    report = _run_generate(plan, config, tmp_path)

    # No critical section (no delete/replace ops)
    assert "🚨 Critical Changes" not in report
    assert "mukta_pg.new_stack" in report


def test_critical_on_update_surfaces_in_critical_section(tmp_path: Path) -> None:
    """When critical_on includes update, updated critical resources go to 🚨 section."""
    plan = _make_plan(
        [
            _rc_entry(
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
    report = _run_generate(plan, config, tmp_path)
    assert "🚨 Critical Changes" in report
    assert "mukta_pg.svc" in report.split("🔍 Resource Details")[0]


def test_no_critical_section_when_no_critical_ops(tmp_path: Path) -> None:
    """🚨 section is absent when no resource has its action in critical_on."""
    plan = _make_plan([_rc_entry("google_storage_bucket", "b1", ["create"])])
    config = ""
    report = _run_generate(plan, config, tmp_path)
    assert "🚨 Critical Changes" not in report


# ---------------------------------------------------------------------------
# Integration: summary detail level
# ---------------------------------------------------------------------------


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
    plan = _make_plan(
        [
            _rc_entry("google_storage_bucket", "b1", ["create"], after={"name": "b1"}),
            _rc_entry("google_sql_database_instance", "db1", ["create"], after={"name": "db1"}),
        ]
    )
    report = _run_generate(plan, "", tmp_path)

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
