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


def _assert_html_elements_balanced(report: str) -> None:
    """Assert no rendered fragment opened or closed one of the report's own HTML elements."""
    for element in ("details", "summary"):
        assert report.count(f"<{element}>") == report.count(f"</{element}>")
    for summary_line in [line for line in report.splitlines() if "<summary>" in line]:
        assert summary_line.count("<summary>") == summary_line.count("</summary>") == 1


# ---------------------------------------------------------------------------
# Known reason phrasing (task 5.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("address", "expected_fragment"),
    [
        pytest.param("null_resource.tainted", "the resource is tainted", id="replace-reason-reaches-the-block"),
    ],
)
def test_known_reason_renders_as_neutral_prose(tmp_path: Path, address: str, expected_fragment: str) -> None:
    """A known reason code reaches the rendered block as neutral prose, not the raw code.

    Every code's phrasing is pinned by `tests/test_causation.py`; this asserts the wiring.
    """
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

    forces_line = next(line for line in report.splitlines() if line.startswith("**Forces replacement:**"))
    # The hostile key arrives on one physical line, with its line feed a visible escape.
    assert "line2" in forces_line
    # The key's backtick cannot close the code span the template opened around the path.
    assert forces_line.count("`") % 2 == 0
    assert r"\u0060" in forces_line
    # A pipe is ordinary text in a paragraph, and the line is no table row, so the report keeps
    # saying what the plan said rather than mutating it.
    assert "| pipe" in forces_line
    assert not forces_line.lstrip().startswith("|")
    # The block's own attribute table is untouched: three rows of exactly four delimiters, so a
    # fragment leaking into a cell would change the count rather than pass unnoticed.
    table_rows = [line for line in block.splitlines() if line.strip().startswith("|")]
    assert [_count_table_columns(row) for row in table_rows] == [4, 4, 4]

    summary_line = next(line for line in report.splitlines() if "hostile" in line and "<summary>" in line)
    # The summary fragment renders markup as literal content, and opens no element of its own.
    assert "<script>" not in summary_line
    assert "&lt;script&gt;" in summary_line
    assert summary_line.endswith("</summary>")
    _assert_html_elements_balanced(report)


def test_hostile_reason_cannot_inject_markup_or_close_the_block(tmp_path: Path) -> None:
    """A hostile `action_reason` reaches an HTML-capable Markdown paragraph and must stay inert."""
    report = _run_generate("causation-hostile-reason.json", tmp_path)

    reason_line = next(line for line in report.splitlines() if line.startswith("**Reason:**"))
    # No tag can open: the reason is entity-escaped, so `</details>` cannot close the block.
    assert "<" not in reason_line
    assert "&lt;/details>" in reason_line
    assert "&lt;img src=x onerror=alert(1)>" in reason_line
    # The raw line feed collapsed, so the injected heading is not a heading and not a new line.
    assert "# Injected Heading" in reason_line
    assert "\\n" in reason_line
    # The backtick cannot open a code span, and the ampersand renders as itself.
    assert "&#96;code&#96;" in reason_line
    assert "&amp;" in reason_line
    _assert_html_elements_balanced(report)

    summary_line = next(line for line in report.splitlines() if "hostile_reason" in line and "<summary>" in line)
    assert "<" not in summary_line.removeprefix("<summary><b>").removesuffix("</summary>").replace("</b>", "")


def test_non_replace_change_carrying_forcing_paths_states_no_replacement(tmp_path: Path) -> None:
    """`replace_paths` on an update explains nothing, so the report must not claim a replacement."""
    report = _run_generate("causation-non-replace-paths.json", tmp_path)
    block = _resource_block(report, "aws_instance.updated_with_paths")

    assert "**Forces replacement:**" not in block
    assert "**Mechanism:**" not in block
    assert "forces replacement:" not in report
    # The stated reason still reaches the block: only the replacement claim is withheld.
    assert "the resource is tainted" in block


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
# Sensitivity (task 5.5)
# ---------------------------------------------------------------------------


def test_sensitive_forcing_path_never_names_more_than_the_masked_table_row(tmp_path: Path) -> None:
    """A path descending into a masked value is cut to the attribute the table already shows."""
    report = _run_generate("causation-sensitive-path.json", tmp_path)
    block = _resource_block(report, "aws_lambda_function.env")

    assert "STRIPE_LIVE_KEY" not in report
    assert "sk_live_old" not in report
    assert "sk_live_new" not in report
    assert "**Forces replacement:** `environment`" in block
    assert re.search(r"`environment`.*\(sensitive value\)", block)


def test_sensitive_forcing_path_is_shown_while_its_value_stays_masked(tmp_path: Path) -> None:
    """A forcing path naming a sensitive attribute is presented, but the value stays masked."""
    report = _run_generate("causation-sensitive-path.json", tmp_path)
    block = _resource_block(report, "aws_db_instance.creds")
    assert "**Forces replacement:** `password`" in block
    assert "old-secret" not in block
    assert "new-secret" not in block
    assert re.search(r"`password`.*\(sensitive value\)", block)
