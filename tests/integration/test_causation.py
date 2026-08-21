"""Integration coverage for the `plan-causation-rendering` capability.

Exercises `replace_paths`/`action_reason` end to end through the CLI, across both the
collapsed `<summary>` line (HTML context) and the detail-block body (Markdown context).
"""

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tf_peek.cli import app

_FIXTURES = Path(__file__).parent / "fixtures"


def _run_generate(fixture_name: str, tmp_path: Path) -> str:
    """Render a fixture plan through the CLI's `--output` path and return the report text."""
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")
    output_file = tmp_path / "report.md"
    args = [str(_FIXTURES / fixture_name), "--config", str(config_file), "--output", str(output_file)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    return output_file.read_text()


def _resource_block(report: str, address: str) -> str:
    """Slice out one resource's `<details>...</details>` block by its address line."""
    start = report.index(f"*`{address}`*")
    end = report.index("</details>", start)
    return report[start:end]


def _count_table_columns(row: str) -> int:
    r"""Count physical Markdown table delimiters, honoring backslash escapes."""
    count = 0
    escaped = False
    for ch in row:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "|":
            count += 1
    return count


# ---------------------------------------------------------------------------
# Known reason phrasing (task 5.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("address", "expected_fragment"),
    [
        pytest.param("null_resource.tainted", "tainted", id="tainted"),
        pytest.param(
            "aws_instance.requested",
            "explicitly requested when the plan was created",
            id="replace-by-request",
        ),
        pytest.param(
            "aws_instance.triggered",
            "configured replacement triggers selected the replacement",
            id="replace-by-triggers",
        ),
        pytest.param(
            "google_storage_bucket.no_resource_config",
            "Terraform found no corresponding resource configuration",
            id="delete-no-resource-config",
        ),
        pytest.param(
            "google_storage_bucket.each_key_gone",
            "for_each key no longer matches",
            id="delete-each-key",
        ),
        pytest.param(
            "google_storage_bucket.move_target_gone",
            "moved block",
            id="delete-no-move-target",
        ),
    ],
)
def test_known_reason_renders_as_neutral_prose(tmp_path: Path, address: str, expected_fragment: str) -> None:
    """Every known non-read reason code renders as neutral prose in the resource's block."""
    report = _run_generate("causation-reasons.json", tmp_path)
    block = _resource_block(report, address)
    assert expected_fragment in block


def test_unknown_deletion_reason_is_passed_through_and_marked(tmp_path: Path) -> None:
    """An unrecognized reason code renders successfully, verbatim, marked as passed through."""
    report = _run_generate("causation-reasons.json", tmp_path)
    block = _resource_block(report, "google_storage_bucket.future_reason")
    assert "delete_because_a_future_terraform_release" in block
    assert "reported by Terraform" in block


# ---------------------------------------------------------------------------
# Precedence rule (task 5.1)
# ---------------------------------------------------------------------------


def test_cannot_update_reason_is_suppressed_when_paths_present(tmp_path: Path) -> None:
    """Paths plus `replace_because_cannot_update` render only the paths."""
    report = _run_generate("causation-precedence.json", tmp_path)
    block = _resource_block(report, "google_sql_database_instance.cannot_update")
    assert "**Forces replacement:** `engine_version`" in block
    assert "**Reason:**" not in block


def test_unknown_reason_alongside_paths_is_preserved(tmp_path: Path) -> None:
    """An unrecognized reason alongside paths is not treated as redundant and stays visible."""
    report = _run_generate("causation-precedence.json", tmp_path)
    block = _resource_block(report, "google_sql_database_instance.non_redundant")
    assert "**Forces replacement:** `engine_version`" in block
    assert "**Reason:**" in block
    assert "replace_because_a_future_terraform_release" in block


def test_replacement_with_neither_field_has_no_explanation(tmp_path: Path) -> None:
    """A replacement stating neither paths nor a reason gets no explanation, but still renders."""
    report = _run_generate("causation-precedence.json", tmp_path)
    block = _resource_block(report, "aws_instance.no_cause")
    assert "**Forces replacement:**" not in block
    assert "**Reason:**" not in block
    # The mechanism is unconditional for a replace and is unaffected by causation being absent.
    assert "**Mechanism:**" in block
    # The attribute diff itself is unaffected.
    assert '`"ami-old"`' in block
    assert '`"ami-new"`' in block


# ---------------------------------------------------------------------------
# Hostile map key (task 5.2)
# ---------------------------------------------------------------------------


def test_hostile_forcing_path_stays_structurally_safe(tmp_path: Path) -> None:
    """A pipe, backtick, line feed and HTML-like text in a forcing path cannot corrupt the report."""
    report = _run_generate("causation-hostile-path.json", tmp_path)
    block = _resource_block(report, "google_project_iam_member.hostile")

    # A raw hostile map key never reaches the report on one physical line: it is either
    # escaped (body) or HTML-entity-encoded (summary), and its embedded newline is a visible
    # `\n` escape rather than an actual line break in both.
    forces_line = next(line for line in report.splitlines() if line.startswith("**Forces replacement:**"))
    assert "line2" in forces_line

    # The Markdown body neutralizes pipe/backtick as literal escape text.
    assert r"\u007c" in block
    assert r"\u0060" in block

    # The resource's own attribute-diff table keeps a consistent column count.
    table_rows = [line for line in block.splitlines() if line.strip().startswith("|")]
    assert table_rows
    assert len({_count_table_columns(row) for row in table_rows}) == 1

    # The collapsed summary line HTML-escapes markup so it renders as literal content.
    summary_line = next(line for line in report.splitlines() if "hostile" in line and "<summary>" in line)
    assert "<script>" not in summary_line
    assert "&lt;script&gt;" in summary_line
    assert summary_line.count("\n") == 0


# ---------------------------------------------------------------------------
# Summary cap, sorting and de-duplication (tasks 5.1, 5.3)
# ---------------------------------------------------------------------------


def test_multi_path_summary_is_capped_with_remainder_and_body_has_full_sorted_list(tmp_path: Path) -> None:
    """The summary line caps forcing paths with a remainder note; the body lists every path, sorted."""
    report = _run_generate("causation-multi-path.json", tmp_path)

    summary_line = next(line for line in report.splitlines() if "many_paths" in line and "<summary>" in line)
    assert summary_line.count("<code>") == 3  # noqa: PLR2004 — the summary path cap
    assert "(+2 more)" in summary_line

    block = _resource_block(report, "kubernetes_deployment.many_paths")
    assert "**Forces replacement:** `alpha`, `bravo`, `delta`, `mango`, `zeta`" in block


# ---------------------------------------------------------------------------
# Replacement mechanism (task 5.1)
# ---------------------------------------------------------------------------


def test_create_before_destroy_states_the_opposite_mechanism(tmp_path: Path) -> None:
    """A `["create", "delete"]` replacement states that it creates before destroying."""
    report = _run_generate("causation-create-before-destroy.json", tmp_path)
    block = _resource_block(report, "aws_launch_template.cbd")
    assert "the replacement is created before the existing object is destroyed" in block
    assert "**Forces replacement:** `image_id`" in block


# ---------------------------------------------------------------------------
# Sensitivity is unaffected (task 5.5)
# ---------------------------------------------------------------------------


def test_sensitive_forcing_path_is_shown_while_its_value_stays_masked(tmp_path: Path) -> None:
    """A forcing path naming a sensitive attribute is presented, but the value stays masked."""
    report = _run_generate("causation-sensitive-path.json", tmp_path)
    block = _resource_block(report, "aws_db_instance.creds")
    assert "**Forces replacement:** `password`" in block
    assert "old-secret" not in block
    assert "new-secret" not in block
    assert re.search(r"`password`.*\(sensitive value\)", block)
