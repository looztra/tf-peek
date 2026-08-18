"""Tests for the ``--fail-on-critical`` / ``--fail-on-critical-on`` exit-code gate."""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from tests.helpers import make_plan, rc_entry, run_generate_raw
from tf_peek.actions import ACTION_ORDER, Action
from tf_peek.cli import _gate_triggered, app

# ---------------------------------------------------------------------------
# Integration: --fail-on-critical / --fail-on-critical-on gate
# ---------------------------------------------------------------------------


def test_fail_on_critical_absent_exits_zero(tmp_path: Path) -> None:
    """No gate flag passed: a critical delete is rendered but the process exits 0 as today."""
    plan = make_plan([rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    result = run_generate_raw(plan, config, tmp_path, [])
    assert result.exit_code == 0, result.output
    report = (tmp_path / "report.md").read_text()
    assert "🚨 Critical Changes" in report


def test_fail_on_critical_triggers_on_default_scope(tmp_path: Path) -> None:
    """--fail-on-critical exits 3 when the rendered 🚨 section is non-empty, report still written."""
    plan = make_plan([rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    result = run_generate_raw(plan, config, tmp_path, ["--fail-on-critical"])
    assert result.exit_code == 3, result.output  # noqa: PLR2004 — critical gate exit code
    report = (tmp_path / "report.md").read_text()
    assert "🚨 Critical Changes" in report
    assert "mukta_pg.prod" in report


def test_fail_on_critical_no_critical_resources_exits_zero(tmp_path: Path) -> None:
    """--fail-on-critical passed but no critical-tier resources present: exits 0."""
    plan = make_plan([rc_entry("google_storage_bucket", "b1", ["create"])])
    result = run_generate_raw(plan, "", tmp_path, ["--fail-on-critical"])
    assert result.exit_code == 0, result.output


def test_fail_on_critical_on_scoped_action_present(tmp_path: Path) -> None:
    """--fail-on-critical-on delete triggers on a critical delete even outside its own critical_on.

    The resource's own `critical_on` is `["replace"]` only, so it would NOT appear in the 🚨
    section — the scoped gate must not go through `critical_resources_by_action`.
    """
    plan = make_plan([rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
critical_on = ["replace"]
"""
    result = run_generate_raw(plan, config, tmp_path, ["--fail-on-critical-on", "delete"])
    assert result.exit_code == 3, result.output  # noqa: PLR2004 — critical gate exit code
    report = (tmp_path / "report.md").read_text()
    assert "🚨 Critical Changes" not in report


def test_fail_on_critical_on_divergence_from_rendered_section(tmp_path: Path) -> None:
    """--fail-on-critical-on delete exits 0 even though the report's 🚨 section shows a replace."""
    plan = make_plan(
        [
            rc_entry(
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
    result = run_generate_raw(plan, config, tmp_path, ["--fail-on-critical-on", "delete"])
    assert result.exit_code == 0, result.output
    report = (tmp_path / "report.md").read_text()
    assert "🚨 Critical Changes" in report


def test_fail_on_critical_on_multiple_actions(tmp_path: Path) -> None:
    """Two --fail-on-critical-on occurrences: a resource matching either triggers exit 3."""
    plan = make_plan(
        [
            rc_entry(
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
    result = run_generate_raw(
        plan, config, tmp_path, ["--fail-on-critical-on", "delete", "--fail-on-critical-on", "replace"]
    )
    assert result.exit_code == 3, result.output  # noqa: PLR2004 — critical gate exit code


def test_fail_on_critical_on_invalid_action_is_usage_error(tmp_path: Path) -> None:
    """An unrecognized --fail-on-critical-on value is a usage error; no report is written."""
    plan = make_plan([rc_entry("google_storage_bucket", "b1", ["create"])])
    result = run_generate_raw(plan, "", tmp_path, ["--fail-on-critical-on", "destroy"])
    assert result.exit_code == 2, result.output  # noqa: PLR2004 — click "usage error" exit code
    assert not (tmp_path / "report.md").exists()


def test_fail_on_critical_on_takes_precedence_when_both_flags_passed(tmp_path: Path) -> None:
    """Both flags passed: --fail-on-critical-on's scope wins over --fail-on-critical's broader one."""
    plan = make_plan(
        [
            rc_entry(
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
    result = run_generate_raw(plan, config, tmp_path, ["--fail-on-critical", "--fail-on-critical-on", "delete"])
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Drift guards and report-decoupling invariants (adversarial review hardening)
# ---------------------------------------------------------------------------


def test_gate_flags_do_not_change_report_bytes(tmp_path: Path) -> None:
    """Spec: the flags SHALL NOT change the rendered report — only the exit status.

    Runs the same plan/config with and without each gate flag and asserts the written report
    bytes are identical, so a future refactor threading a flag into ``template.render`` is caught.
    """
    plan = make_plan([rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    baseline = run_generate_raw(plan, config, tmp_path, [])
    assert baseline.exit_code == 0, baseline.output
    baseline_report = (tmp_path / "report.md").read_text()

    for gate_flag in (["--fail-on-critical"], ["--fail-on-critical-on", "delete"]):
        # tmp_path is reused across iterations; the helper overwrites report.md each call.
        flagged = run_generate_raw(plan, config, tmp_path, gate_flag)
        assert flagged.exit_code == 3, flagged.output  # noqa: PLR2004 — critical gate exit code
        assert (tmp_path / "report.md").read_text() == baseline_report


def test_fail_on_critical_default_uses_rendered_section_not_raw_tier(tmp_path: Path) -> None:
    """--fail-on-critical must read the filtered 🚨 structure, not the unfiltered per-action tally.

    A critical-tier ``create`` whose own ``critical_on`` excludes ``create`` is NOT rendered in 🚨,
    so the default gate must exit 0 — even though ``critical_tier_actions_seen`` contains ``create``.
    A swap of the two data structures in ``_gate_triggered`` would mis-fire here.
    """
    plan = make_plan([rc_entry("mukta_pg", "prod", ["create"], after={"plan": "business-8"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
critical_on = ["delete", "replace"]
"""
    result = run_generate_raw(plan, config, tmp_path, ["--fail-on-critical"])
    assert result.exit_code == 0, result.output
    report = (tmp_path / "report.md").read_text()
    assert "🚨 Critical Changes" not in report


def test_fail_on_critical_on_invalid_action_emits_no_report_on_stdout(tmp_path: Path) -> None:
    """Invalid --fail-on-critical-on value exits 2 with no report on stdout either.

    The companion file-output test only checks the report file is absent; this pins that nothing
    is echoed to stdout before typer rejects the value — ``generate()`` is never entered.
    """
    plan = make_plan([rc_entry("google_storage_bucket", "b1", ["create"])])
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
    plan = make_plan([rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
"""
    result = run_generate_raw(
        plan, config, tmp_path, ["--fail-on-critical-on", "delete", "--fail-on-critical-on", "delete"]
    )
    assert result.exit_code == 3, result.output  # noqa: PLR2004 — critical gate exit code


def test_fail_on_critical_on_all_actions_ignores_critical_on(tmp_path: Path) -> None:
    """All four actions enumerated: triggers on a critical create even outside its critical_on.

    Distinct from --fail-on-critical (which would exit 0 here, since create is not in
    critical_on) — pins that the scoped flag evaluates the raw tier, not the rendered section.
    """
    plan = make_plan([rc_entry("mukta_pg", "prod", ["create"], after={"plan": "business-8"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
critical_on = ["delete", "replace"]
"""
    result = run_generate_raw(
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
    plan = make_plan([])
    result = run_generate_raw(plan, "", tmp_path, extra_args)
    assert result.exit_code == 0, result.output


def test_fail_on_critical_on_with_empty_critical_on_config(tmp_path: Path) -> None:
    """A critical resource whose critical_on=[] never reaches 🚨, but the scoped gate still fires.

    Pins the report/gate decoupling at the empty-list boundary: the default flag sees an empty 🚨
    section (exit 0) while the scoped flag sees the raw critical tier (exit 3).
    """
    plan = make_plan([rc_entry("mukta_pg", "prod", ["delete"], before={"plan": "business-4"})])
    config = """
[[resources]]
match_type = "mukta_pg"
tier = "critical"
critical_on = []
"""
    default_result = run_generate_raw(plan, config, tmp_path, ["--fail-on-critical"])
    assert default_result.exit_code == 0, default_result.output
    assert "🚨 Critical Changes" not in (tmp_path / "report.md").read_text()

    scoped_result = run_generate_raw(plan, config, tmp_path, ["--fail-on-critical-on", "delete"])
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
