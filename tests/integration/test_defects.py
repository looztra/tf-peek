"""Defect ledger for the six issues catalogued in `docs/studies/2026-08-15-capability-and-market-analysis.md §4.1`.

Each assertion below is `@pytest.mark.xfail(strict=True, ...)`: it currently fails for
exactly the stated reason, and `strict=True` turns an unexpected pass (a fix landing
without the marker being removed) into a CI failure. This makes the ledger executable
and self-maintaining rather than a comment that can silently rot.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tf_peek.main import app, calculate_diff

_FIXTURES = Path(__file__).parent / "fixtures"


def _run_generate(fixture_name: str, tmp_path: Path) -> str:
    """Render a fixture plan through the CLI and return the rendered Markdown."""
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")
    output_file = tmp_path / "report.md"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            str(_FIXTURES / fixture_name),
            "--config",
            str(config_file),
            "--output",
            str(output_file),
        ],
    )
    assert result.exit_code == 0, result.output
    return output_file.read_text()


# ---------------------------------------------------------------------------
# D1 — sensitive values leaked in plaintext
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="D1: sensitive values are leaked in plaintext")
def test_sensitive_values_not_leaked(tmp_path: Path) -> None:
    """No sensitive value should ever appear in the rendered report."""
    report = _run_generate("sensitive.json", tmp_path)
    assert "hunter2" not in report
    assert "s3cr3t!" not in report


# ---------------------------------------------------------------------------
# D3 — hostile strings (pipe + newline) break the Markdown table
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="D3: unescaped values break the Markdown table")
def test_hostile_strings_do_not_break_table(tmp_path: Path) -> None:
    """Assert the resource-details table survives a hostile value intact.

    Every row must have a consistent column count and no cell may contain a raw
    newline — both break Markdown table rendering, and a raw pipe additionally
    adds a phantom column.
    """
    report = _run_generate("hostile-strings.json", tmp_path)

    # The unescaped value's embedded newline splits the row: this exact
    # substring only appears verbatim while the raw newline reaches the output.
    assert "has | pipe\nand a newline" not in report, "cell contains a raw newline"

    detail_idx = report.find("🔍 Resource Details")
    table_rows = [line for line in report[detail_idx:].splitlines() if line.strip().startswith("|")]
    assert table_rows, "no table rows found in resource details"
    column_counts = {row.count("|") for row in table_rows}
    assert len(column_counts) == 1, "table rows have inconsistent column counts"


# ---------------------------------------------------------------------------
# D4 — nested structures dumped as Python repr
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="D4: nested structures are dumped as Python repr, not JSON")
def test_nested_values_rendered_as_json(tmp_path: Path) -> None:
    """Nested dict/list values must render as JSON, not Python `repr`."""
    report = _run_generate("nested-unknown.json", tmp_path)
    assert "'tier'" not in report, "Python repr single-quoted key found"
    assert "None" not in report, "Python repr None literal found instead of JSON null"


# ---------------------------------------------------------------------------
# D5 — nested after_unknown is missed
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="D5: nested after_unknown is silently dropped")
def test_nested_after_unknown_surfaces(tmp_path: Path) -> None:
    """A value known-after-apply nested inside a block must be surfaced, not dropped."""
    report = _run_generate("nested-unknown.json", tmp_path)
    assert "known after apply" in report


# ---------------------------------------------------------------------------
# D2 — report output is not reproducible across runs
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="D2: report output is not reproducible across runs")
def test_determinism_across_hash_seeds(tmp_path: Path) -> None:
    """Assert byte-identical output across fresh interpreters.

    The same plan run through fresh interpreters under differing PYTHONHASHSEED
    values must produce byte-identical output.
    """
    plan_file = _FIXTURES / "kitchen-sink.json"
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")

    outputs = set()
    for seed in range(5):
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


@pytest.mark.xfail(strict=True, reason="D2: calculate_diff iterates an unsorted set, so key order is unstable")
def test_calculate_diff_returns_sorted_keys() -> None:
    """Fast in-process companion to the subprocess determinism test.

    The subprocess test proves the non-determinism property; this one locates
    the break (unsorted key iteration).
    """
    before = {"zebra": "a", "mango": "b", "apple": "c"}
    after = {"zebra": "x", "mango": "y", "apple": "z"}
    diff = calculate_diff(before, after, None)
    assert list(diff.keys()) == sorted(diff.keys())
