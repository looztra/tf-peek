"""Defect ledger for the six issues catalogued in `docs/studies/2026-08-15-capability-and-market-analysis.md §4.1`.

D1-D5 are resolved; every assertion below is a required passing regression.
D6 (documented CLI invocation) is a separate, out-of-scope documentation defect.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Literal

from typer.testing import CliRunner

from tf_peek.main import app, calculate_diff

_FIXTURES = Path(__file__).parent / "fixtures"


def _run_generate(
    fixture_name: str,
    tmp_path: Path,
    extra_args: list[str] | None = None,
    *,
    destination: Literal["file", "stdout"] = "file",
) -> bytes:
    """Render a fixture plan through the CLI and return the raw report bytes.

    `destination="file"` (the default) drives the `--output` file path and returns
    its bytes; `destination="stdout"` omits `--output` and returns the CLI's
    captured stdout bytes instead, so both destinations can be compared for parity.
    """
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")
    output_file = tmp_path / "report.md"
    args = [str(_FIXTURES / fixture_name), "--config", str(config_file)]
    if destination == "file":
        args += ["--output", str(output_file)]
    result = CliRunner().invoke(app, [*args, *(extra_args or [])])
    assert result.exit_code == 0, result.output
    return output_file.read_bytes() if destination == "file" else result.stdout_bytes


# ---------------------------------------------------------------------------
# D1 — sensitive values leaked in plaintext
# ---------------------------------------------------------------------------


def test_sensitive_values_not_leaked(tmp_path: Path) -> None:
    """No sensitive value should ever appear in the rendered report."""
    report = _run_generate("sensitive.json", tmp_path).decode()
    assert "hunter2" not in report
    assert "s3cr3t!" not in report


def test_nested_sensitivity_masks_entire_attribute(tmp_path: Path) -> None:
    """A sensitivity marker nested inside a block masks the whole top-level attribute."""
    report = _run_generate("nested-sensitive.json", tmp_path).decode()
    assert "hunter2" not in report
    assert "db-f1-micro" not in report
    assert "db-n1-standard-1" not in report
    assert "(sensitive value)" in report


def test_one_sided_sensitivity_masks_both_values(tmp_path: Path) -> None:
    """An attribute sensitive on only one side still masks both before and after."""
    report = _run_generate("one-sided-sensitive.json", tmp_path).decode()
    assert "was-plaintext" not in report
    assert "now-secret" not in report
    assert "(sensitive value)" in report


def test_show_sensitive_flag_renders_underlying_values(tmp_path: Path) -> None:
    """--show-sensitive opts out of masking and renders underlying values."""
    report = _run_generate("sensitive.json", tmp_path, ["--show-sensitive"]).decode()
    assert "hunter2" in report
    assert "s3cr3t!" in report


def test_sensitive_structured_value_with_control_characters_masked(tmp_path: Path) -> None:
    """A sensitive structured value containing pipes/newlines never leaks its content."""
    report = _run_generate("sensitive-structured-hostile.json", tmp_path).decode()
    assert "old | secret" not in report
    assert "new | secret" not in report
    assert "line2" not in report
    assert "(sensitive value)" in report


# ---------------------------------------------------------------------------
# D3 — hostile strings (pipe + newline) break the Markdown table
# ---------------------------------------------------------------------------


def test_hostile_strings_do_not_break_table(tmp_path: Path) -> None:
    """Assert the resource-details table survives a hostile value intact.

    Every row must have a consistent count of unescaped column delimiters and no
    cell may contain a raw newline — both break Markdown table rendering.
    """
    report = _run_generate("hostile-strings.json", tmp_path).decode()

    # The unescaped value's embedded newline splits the row: this exact
    # substring only appears verbatim while the raw newline reaches the output.
    assert "has | pipe\nand a newline" not in report, "cell contains a raw newline"
    assert "has \\| pipe\\nand a newline" in report, "pipe was not Markdown-escaped"

    detail_idx = report.find("🔍 Resource Details")
    table_rows = [line for line in report[detail_idx:].splitlines() if line.strip().startswith("|")]
    column_counts = {len(re.findall(r"(?<!\\)\|", row)) for row in table_rows}
    assert len(column_counts) == 1, "table rows have inconsistent column counts"


def test_structured_hostile_value_is_markdown_safe_valid_json(tmp_path: Path) -> None:
    """A structured value containing a pipe/newline stays one row and valid JSON."""
    report = _run_generate("structured-hostile.json", tmp_path).decode()

    match = re.search(
        r"^\| `metadata` \| `(?P<before>.*)` \| `(?P<after>.*)` \|$",
        report,
        re.MULTILINE,
    )
    assert match is not None, "metadata row is missing or spans physical lines"
    assert json.loads(match.group("after")) == {"message": "new | value\nline2"}


# ---------------------------------------------------------------------------
# D4 — nested structures dumped as Python repr
# ---------------------------------------------------------------------------


def test_nested_values_rendered_as_json(tmp_path: Path) -> None:
    """Nested dict/list values must render as JSON, not Python `repr`."""
    report = _run_generate("nested-unknown.json", tmp_path).decode()
    assert "'tier'" not in report, "Python repr single-quoted key found"
    assert "None" not in report, "Python repr None literal found instead of JSON null"
    assert '"note": null' in report


# ---------------------------------------------------------------------------
# D5 — nested after_unknown is missed
# ---------------------------------------------------------------------------


def test_nested_after_unknown_surfaces(tmp_path: Path) -> None:
    """A value known-after-apply nested inside a block must be surfaced, not dropped."""
    report = _run_generate("nested-unknown.json", tmp_path).decode()
    assert "known after apply" in report


def test_nested_after_unknown_surfaces_for_list_element(tmp_path: Path) -> None:
    """A truthy `after_unknown` marker for a list element/index is surfaced, not dropped."""
    report = _run_generate("nested-unknown-list.json", tmp_path).decode()
    assert "known after apply" in report
    assert '"prod"' in report, "known list element must retain its concrete value"
    assert '`["prod", "(known after apply) ⏳"]`' in report


def test_mismatched_unknown_marker_retains_concrete_value() -> None:
    """A malformed container marker cannot replace a concrete scalar value."""
    diff = calculate_diff(
        {"config": "old-value"},
        {"config": "raw-string"},
        {"config": {"nested": True}},
    )
    assert diff["config"] == {"before": "old-value", "after": "raw-string"}


def test_nested_marker_only_container_surfaces() -> None:
    """A marker-only nested container must surface even when absent from `after`."""
    diff = calculate_diff({}, {}, {"network": {"endpoint": {"host": True}}})
    assert diff == {
        "network": {"before": None, "after": {"endpoint": {"host": "(known after apply) ⏳"}}},
    }


def test_trailing_false_list_markers_do_not_create_values() -> None:
    """Trailing false/None list markers must not create phantom `null` values."""
    diff = calculate_diff({"tags": ["prod"]}, {"tags": ["prod"]}, {"tags": [False, False, None]})
    assert not diff


def test_marker_only_list_preserves_gap_before_unknown() -> None:
    """A leading false list marker is preserved as a gap so a later unknown keeps its index."""
    diff = calculate_diff({}, {}, {"slots": [False, {"id": True}, False]})
    assert diff["slots"]["after"] == [None, {"id": "(known after apply) ⏳"}]


def test_stdout_matches_file_and_preserves_json_list_literals(tmp_path: Path) -> None:
    """Stdout and `--output` render byte-identical Markdown; JSON list literals survive."""
    file_report = _run_generate("stdout-json-list.json", tmp_path, destination="file")
    stdout_report = _run_generate("stdout-json-list.json", tmp_path, destination="stdout")
    assert stdout_report == file_report
    assert b"[true, false, null]" in stdout_report


# ---------------------------------------------------------------------------
# D2 — report output is not reproducible across runs
# ---------------------------------------------------------------------------


def test_determinism_across_hash_seeds(tmp_path: Path) -> None:
    """Assert byte-identical output across fresh interpreters.

    The same plan run through fresh interpreters under differing PYTHONHASHSEED
    values must produce byte-identical output.
    """
    plan_file = _FIXTURES / "kitchen-sink.json"
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")

    outputs = set()
    for seed in range(20):
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "tf_peek.main",
                str(plan_file),
                "--config",
                str(config_file),
            ],
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.add(result.stdout)

    assert len(outputs) == 1, "report output differs across PYTHONHASHSEED values"


def test_calculate_diff_returns_sorted_keys() -> None:
    """Fast in-process companion to the subprocess determinism test.

    The subprocess test proves the non-determinism property; this one locates
    the break (unsorted key iteration). Includes a key present only in
    `after_unknown` to confirm unknown-only keys are merged into the same
    lexical order as before/after keys, not appended out of order.
    """
    before = {"zebra": "a", "mango": "b", "apple": "c"}
    after = {"zebra": "x", "mango": "y", "apple": "z"}
    unknown = {"banana": True}
    diff = calculate_diff(before, after, unknown)
    assert list(diff.keys()) == sorted(diff.keys())
    assert list(diff.keys()) == ["apple", "banana", "mango", "zebra"]
