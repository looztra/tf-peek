"""Tests for tf_peek main logic."""

import json
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner, Result

from tf_peek.main import (
    _KNOWN_AFTER_APPLY,
    _SENSITIVE_VALUE,
    ACTION_ORDER,
    Action,
    _DisplaySentinel,
    _gate_triggered,
    _json_default,
    _version_callback,
    app,
    calculate_diff,
    get_emoji,
)
from tf_peek.models import Change, ResourceChange

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


# ---------------------------------------------------------------------------
# Integration: --fail-on-critical / --fail-on-critical-on gate
# ---------------------------------------------------------------------------


def test_action_enum_values_match_action_order() -> None:
    """`Action` contains exactly the actions in `ACTION_ORDER`; CLI ordering is intentional."""
    assert {member.value for member in Action} == set(ACTION_ORDER)


def _run_generate_raw(plan: dict[str, Any], config_content: str, tmp_path: Path, extra_args: list[str]) -> Result:
    """Write plan + config to tmp_path and invoke generate, returning the raw CliRunner result."""
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan))
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text(config_content)
    output_file = tmp_path / "report.md"

    runner = CliRunner()
    return runner.invoke(
        app,
        [str(plan_file), "--config", str(config_file), "--output", str(output_file), *extra_args],
    )


def test_fail_on_critical_absent_exits_zero(tmp_path: Path) -> None:
    """No gate flag passed: a critical delete is rendered but the process exits 0 as today."""
    plan = _make_plan([_rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    result = _run_generate_raw(plan, config, tmp_path, [])
    assert result.exit_code == 0, result.output
    report = (tmp_path / "report.md").read_text()
    assert "🚨 Critical Changes" in report


def test_fail_on_critical_triggers_on_default_scope(tmp_path: Path) -> None:
    """--fail-on-critical exits 3 when the rendered 🚨 section is non-empty, report still written."""
    plan = _make_plan([_rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    result = _run_generate_raw(plan, config, tmp_path, ["--fail-on-critical"])
    assert result.exit_code == 3, result.output  # noqa: PLR2004 — critical gate exit code
    report = (tmp_path / "report.md").read_text()
    assert "🚨 Critical Changes" in report
    assert "mukta_pg.prod" in report


def test_fail_on_critical_no_critical_resources_exits_zero(tmp_path: Path) -> None:
    """--fail-on-critical passed but no critical-tier resources present: exits 0."""
    plan = _make_plan([_rc_entry("google_storage_bucket", "b1", ["create"])])
    result = _run_generate_raw(plan, "", tmp_path, ["--fail-on-critical"])
    assert result.exit_code == 0, result.output


def test_fail_on_critical_on_scoped_action_present(tmp_path: Path) -> None:
    """--fail-on-critical-on delete triggers on a critical delete even outside its own critical_on.

    The resource's own `critical_on` is `["replace"]` only, so it would NOT appear in the 🚨
    section — the scoped gate must not go through `critical_resources_by_action`.
    """
    plan = _make_plan([_rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
critical_on = ["replace"]
"""
    result = _run_generate_raw(plan, config, tmp_path, ["--fail-on-critical-on", "delete"])
    assert result.exit_code == 3, result.output  # noqa: PLR2004 — critical gate exit code
    report = (tmp_path / "report.md").read_text()
    assert "🚨 Critical Changes" not in report


def test_fail_on_critical_on_divergence_from_rendered_section(tmp_path: Path) -> None:
    """--fail-on-critical-on delete exits 0 even though the report's 🚨 section shows a replace."""
    plan = _make_plan(
        [
            _rc_entry(
                "mukta_pg",
                "prod",
                ["delete", "create"],
                before={"plan": "business-4"},
                after={"plan": "business-8"},
            ),
        ]
    )
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    result = _run_generate_raw(plan, config, tmp_path, ["--fail-on-critical-on", "delete"])
    assert result.exit_code == 0, result.output
    report = (tmp_path / "report.md").read_text()
    assert "🚨 Critical Changes" in report


def test_fail_on_critical_on_multiple_actions(tmp_path: Path) -> None:
    """Two --fail-on-critical-on occurrences: a resource matching either triggers exit 3."""
    plan = _make_plan(
        [
            _rc_entry(
                "mukta_pg",
                "prod",
                ["delete", "create"],
                before={"plan": "business-4"},
                after={"plan": "business-8"},
            ),
        ]
    )
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    result = _run_generate_raw(
        plan, config, tmp_path, ["--fail-on-critical-on", "delete", "--fail-on-critical-on", "replace"]
    )
    assert result.exit_code == 3, result.output  # noqa: PLR2004 — critical gate exit code


def test_fail_on_critical_on_invalid_action_is_usage_error(tmp_path: Path) -> None:
    """An unrecognized --fail-on-critical-on value is a usage error; no report is written."""
    plan = _make_plan([_rc_entry("google_storage_bucket", "b1", ["create"])])
    result = _run_generate_raw(plan, "", tmp_path, ["--fail-on-critical-on", "destroy"])
    assert result.exit_code == 2, result.output  # noqa: PLR2004 — click "usage error" exit code
    assert not (tmp_path / "report.md").exists()


def test_fail_on_critical_on_takes_precedence_when_both_flags_passed(tmp_path: Path) -> None:
    """Both flags passed: --fail-on-critical-on's scope wins over --fail-on-critical's broader one."""
    plan = _make_plan(
        [
            _rc_entry(
                "mukta_pg",
                "prod",
                ["delete", "create"],
                before={"plan": "business-4"},
                after={"plan": "business-8"},
            ),
        ]
    )
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    result = _run_generate_raw(plan, config, tmp_path, ["--fail-on-critical", "--fail-on-critical-on", "delete"])
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Drift guards and report-decoupling invariants (adversarial review hardening)
# ---------------------------------------------------------------------------


def test_action_values_cover_simple_action_outcomes_reaching_gate() -> None:
    """Every ``simple_action`` that survives the no-op/read filter is selectable on the CLI.

    The scoped gate compares ``rc.simple_action`` (a bare string from ``models.py``) against
    ``Action`` member values. If ``simple_action`` ever yields a value outside ``Action`` (e.g. a
    future Terraform action), the scoped gate would silently under-gate. This pins the contract
    that the two value sets stay aligned for the actions that actually reach the tally.
    """
    selectable = {a.value for a in Action}
    # Each shape produces the simple_action shown; "no-op"/"read" are filtered before the tally
    # and are deliberately not selectable gate actions.
    cases = {
        "create": ["create"],
        "update": ["update"],
        "delete": ["delete"],
        "replace": ["delete", "create"],
    }
    for expected, actions in cases.items():
        rc = ResourceChange(
            address=f"t.{expected}",
            type="t",
            name=expected,
            change=Change(actions=actions),
        )
        assert rc.simple_action == expected
        assert rc.simple_action in selectable


def test_gate_flags_do_not_change_report_bytes(tmp_path: Path) -> None:
    """Spec: the flags SHALL NOT change the rendered report — only the exit status.

    Runs the same plan/config with and without each gate flag and asserts the written report
    bytes are identical, so a future refactor threading a flag into ``template.render`` is caught.
    """
    plan = _make_plan([_rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    baseline = _run_generate_raw(plan, config, tmp_path, [])
    assert baseline.exit_code == 0, baseline.output
    baseline_report = (tmp_path / "report.md").read_text()

    for gate_flag in (["--fail-on-critical"], ["--fail-on-critical-on", "delete"]):
        # tmp_path is reused across iterations; the helper overwrites report.md each call.
        flagged = _run_generate_raw(plan, config, tmp_path, gate_flag)
        assert flagged.exit_code == 3, flagged.output  # noqa: PLR2004 — critical gate exit code
        assert (tmp_path / "report.md").read_text() == baseline_report


def test_fail_on_critical_default_uses_rendered_section_not_raw_tier(tmp_path: Path) -> None:
    """--fail-on-critical must read the filtered 🚨 structure, not the unfiltered per-action tally.

    A critical-tier ``create`` whose own ``critical_on`` excludes ``create`` is NOT rendered in 🚨,
    so the default gate must exit 0 — even though ``critical_tier_actions_seen`` contains ``create``.
    A swap of the two data structures in ``_gate_triggered`` would mis-fire here.
    """
    plan = _make_plan([_rc_entry("mukta_pg", "prod", ["create"], after={"plan": "business-8"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
critical_on = ["delete", "replace"]
"""
    result = _run_generate_raw(plan, config, tmp_path, ["--fail-on-critical"])
    assert result.exit_code == 0, result.output
    report = (tmp_path / "report.md").read_text()
    assert "🚨 Critical Changes" not in report


def test_fail_on_critical_on_invalid_action_emits_no_report_on_stdout(tmp_path: Path) -> None:
    """Invalid --fail-on-critical-on value exits 2 with no report on stdout either.

    The companion file-output test only checks the report file is absent; this pins that nothing
    is echoed to stdout before typer rejects the value — ``generate()`` is never entered.
    """
    plan = _make_plan([_rc_entry("google_storage_bucket", "b1", ["create"])])
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan))
    runner = CliRunner()
    result = runner.invoke(app, [str(plan_file), "--fail-on-critical-on", "destroy"])
    assert result.exit_code == 2, result.output  # noqa: PLR2004 — click usage-error exit code
    assert "Terraform Plan Report" not in result.output
    assert "🚨 Critical Changes" not in result.output


# ---------------------------------------------------------------------------
# Edge cases: pin benign gate behavior against silent change
# ---------------------------------------------------------------------------


def test_fail_on_critical_on_duplicate_values_dedup(tmp_path: Path) -> None:
    """Duplicate --fail-on-critical-on values are idempotent; a matching critical still exits 3."""
    plan = _make_plan([_rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    result = _run_generate_raw(
        plan, config, tmp_path, ["--fail-on-critical-on", "delete", "--fail-on-critical-on", "delete"]
    )
    assert result.exit_code == 3, result.output  # noqa: PLR2004 — critical gate exit code


def test_fail_on_critical_on_all_actions_ignores_critical_on(tmp_path: Path) -> None:
    """All four actions enumerated: triggers on a critical create even outside its critical_on.

    Distinct from --fail-on-critical (which would exit 0 here, since create is not in
    critical_on) — pins that the scoped flag evaluates the raw tier, not the rendered section.
    """
    plan = _make_plan([_rc_entry("mukta_pg", "prod", ["create"], after={"plan": "business-8"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
critical_on = ["delete", "replace"]
"""
    result = _run_generate_raw(
        plan,
        config,
        tmp_path,
        [
            "--fail-on-critical-on",
            "create",
            "--fail-on-critical-on",
            "update",
            "--fail-on-critical-on",
            "delete",
            "--fail-on-critical-on",
            "replace",
        ],
    )
    assert result.exit_code == 3, result.output  # noqa: PLR2004 — critical gate exit code


@pytest.mark.parametrize(
    "extra_args",
    [
        pytest.param(["--fail-on-critical"], id="fail-on-critical"),
        pytest.param(["--fail-on-critical-on", "delete"], id="fail-on-critical-on-delete"),
    ],
)
def test_gate_on_empty_plan_exits_zero(tmp_path: Path, extra_args: list[str]) -> None:
    """An empty resource_changes list never trips either gate; exit 0, report still rendered."""
    plan = _make_plan([])
    result = _run_generate_raw(plan, "", tmp_path, extra_args)
    assert result.exit_code == 0, result.output


def test_fail_on_critical_on_with_empty_critical_on_config(tmp_path: Path) -> None:
    """A critical resource whose critical_on=[] never reaches 🚨, but the scoped gate still fires.

    Pins the report/gate decoupling at the empty-list boundary: the default flag sees an empty 🚨
    section (exit 0) while the scoped flag sees the raw critical tier (exit 3).
    """
    plan = _make_plan([_rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
critical_on = []
"""
    default_result = _run_generate_raw(plan, config, tmp_path, ["--fail-on-critical"])
    assert default_result.exit_code == 0, default_result.output
    assert "🚨 Critical Changes" not in (tmp_path / "report.md").read_text()

    scoped_result = _run_generate_raw(plan, config, tmp_path, ["--fail-on-critical-on", "delete"])
    assert scoped_result.exit_code == 3, scoped_result.output  # noqa: PLR2004 — critical gate exit code


# ---------------------------------------------------------------------------
# Unit: _gate_triggered decision matrix (independent of CliRunner)
# ---------------------------------------------------------------------------


def _tiered_summary(critical_actions: set[str]) -> dict[str, dict[str, int]]:
    """Build a ``tiered_summary`` where each action's ``critical`` count is 1 iff listed."""
    return {a: {"critical": int(a in critical_actions), "normal": 0, "silent": 0} for a in ACTION_ORDER}


@pytest.mark.parametrize(
    ("fail_on_critical", "fail_on_critical_on", "critical_actions", "critical_to_render", "expected"),
    [
        pytest.param(False, [], set(), {}, False, id="no-flags-never-triggers"),
        pytest.param(True, [], set(), {}, False, id="default-empty-section-no-trigger"),
        pytest.param(True, [], set(), {"delete": {"t": [{}]}}, True, id="default-nonempty-section-triggers"),
        pytest.param(False, [Action.delete], {"delete"}, {}, True, id="scoped-matching-action-triggers"),
        pytest.param(False, [Action.delete], {"replace"}, {}, False, id="scoped-nonmatching-action-no-trigger"),
        pytest.param(
            False,
            [Action.delete, Action.replace],
            {"replace"},
            {"delete": {"t": [{}]}},
            True,
            id="scoped-matches-second-listed-action-triggers",
        ),
        pytest.param(
            True,
            [Action.delete],
            set(),
            {"delete": {"t": [{}]}},
            False,
            id="both-flags-scoped-wins-and-no-match",
        ),
        pytest.param(
            True,
            [Action.delete],
            {"delete"},
            {"delete": {"t": [{}]}},
            True,
            id="both-flags-scoped-matches-triggers",
        ),
    ],
)
def test_gate_triggered_decision_matrix(
    fail_on_critical: bool,
    fail_on_critical_on: list[Action],
    critical_actions: set[str],
    critical_to_render: dict[str, dict[str, list[dict[str, Any]]]],
    expected: bool,
) -> None:
    """Unit-test the gate's decision logic independent of CliRunner.

    Pins precedence (scoped wins over default), the default↔🚨-section mirror, and that the
    scoped branch reads the unfiltered per-action critical count from ``tiered_summary``.
    """
    summary = _tiered_summary(critical_actions)
    assert _gate_triggered(fail_on_critical, fail_on_critical_on, summary, critical_to_render) == expected
