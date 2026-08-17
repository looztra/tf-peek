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

import pytest
from typer.testing import CliRunner

from tf_peek.main import _KNOWN_AFTER_APPLY, _format_report_value, app, calculate_diff

_FIXTURES = Path(__file__).parent / "fixtures"


def _run_generate(fixture_name: str, tmp_path: Path, extra_args: list[str] | None = None) -> bytes:
    """Render a fixture plan through the CLI's `--output` path and return its bytes."""
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")
    output_file = tmp_path / "report.md"
    args = [str(_FIXTURES / fixture_name), "--config", str(config_file), "--output", str(output_file)]
    result = CliRunner().invoke(app, [*args, *(extra_args or [])])
    assert result.exit_code == 0, result.output
    return output_file.read_bytes()


def _count_table_columns(row: str) -> int:
    r"""Count physical Markdown table delimiters with a spec-correct escape scan.

    A backslash escapes the next character; only an unescaped ``|`` is a column
    delimiter. This catches ``\\\\|`` (escaped backslash + live pipe) as a real
    delimiter, which a simple lookbehind regex misses.
    """
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
    # Scalar strings render as JSON-quoted text with `|` as `\u007c`, so the
    # pipe cannot create an additional Markdown table column.
    assert "has \\u007c pipe\\nand a newline" in report, "pipe was not JSON-escaped"

    detail_idx = report.find("🔍 Resource Details")
    table_rows = [line for line in report[detail_idx:].splitlines() if line.strip().startswith("|")]
    assert table_rows, "no table rows found in resource details"
    column_counts = {_count_table_columns(row) for row in table_rows}
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


def test_backticks_in_value_do_not_close_code_span(tmp_path: Path) -> None:
    """A value containing backticks cannot close the cell's code-span wrapper."""
    report = _run_generate("backtick-hostile.json", tmp_path).decode()

    match = re.search(
        r"^\| `script` \| `(?P<before>.*)` \| `(?P<after>.*)` \|$",
        report,
        re.MULTILINE,
    )
    assert match is not None, "script row is missing or spans physical lines"
    after = match.group("after")
    # No raw backtick or pipe reaches the cell: both are neutralized so the
    # value cannot re-pair the template's wrapper backticks or add a column.
    assert "`" not in after, "raw backtick leaked into the rendered cell"
    assert "|" not in after, "raw pipe leaked into the rendered cell"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("", '""', id="empty-string"),
        pytest.param("false", '"false"', id="string-false"),
        pytest.param(False, "false", id="boolean-false"),
        pytest.param(None, "null", id="null"),
        pytest.param(0, "0", id="zero"),
    ],
)
def test_scalars_render_as_distinguishable_json_literals(value: str | bool | int | None, expected: str) -> None:
    """An empty string stays visible and a string `false` stays distinct from a boolean.

    The template previously routed falsy values through a `default('null')` filter,
    which rendered an empty string, a zero and a `false` identically.
    """
    assert _format_report_value(value) == expected


# ---------------------------------------------------------------------------
# D4 — nested structures dumped as Python repr
# ---------------------------------------------------------------------------


def test_nested_values_rendered_as_json(tmp_path: Path) -> None:
    """Nested dict/list values must render as JSON, not Python `repr`."""
    report = _run_generate("nested-unknown.json", tmp_path).decode()

    match = re.search(
        r"^\| `settings` \| `(?P<before>.*)` \| `(?P<after>.*)` \|$",
        report,
        re.MULTILINE,
    )
    assert match is not None, "settings row is missing or spans physical lines"
    after = match.group("after")
    assert "'tier'" not in after, "Python repr single-quoted key found"
    assert "None" not in after, "Python repr None literal found instead of JSON null"
    assert '"note": null' in after


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
    assert '`["prod", "(known after apply) ⏳"]`' in report


@pytest.mark.parametrize(
    "marker",
    [
        pytest.param({"nested": True}, id="dict-marker"),
        pytest.param([True], id="list-marker"),
    ],
)
def test_mismatched_unknown_marker_retains_concrete_value(marker: object) -> None:
    """A malformed container marker cannot replace a concrete scalar value."""
    diff = calculate_diff({"config": "old-value"}, {"config": "raw-string"}, {"config": marker})
    assert diff["config"] == {"before": "old-value", "after": "raw-string"}


def test_nested_marker_only_container_surfaces() -> None:
    """A marker-only nested container must surface even when absent from `after`."""
    diff = calculate_diff({}, {}, {"network": {"endpoint": {"host": True}}})
    assert diff == {
        "network": {"before": None, "after": {"endpoint": {"host": _KNOWN_AFTER_APPLY}}},
    }


def test_trailing_false_list_markers_do_not_create_values() -> None:
    """Trailing false/None list markers must not create phantom `null` values."""
    diff = calculate_diff({"tags": ["prod"]}, {"tags": ["prod"]}, {"tags": [False, False, None]})
    assert not diff


def test_marker_only_list_preserves_gap_before_unknown() -> None:
    """A leading false list marker is preserved as a gap so a later unknown keeps its index."""
    diff = calculate_diff({}, {}, {"slots": [False, {"id": True}, False]})
    assert diff["slots"]["after"] == [None, {"id": _KNOWN_AFTER_APPLY}]


def test_marker_beyond_the_concrete_list_appends_unknown_elements() -> None:
    """A marker index past the end of the concrete list adds that unknown element."""
    diff = calculate_diff({"tags": ["prod"]}, {"tags": ["prod"]}, {"tags": [False, True]})
    assert diff["tags"]["after"] == ["prod", _KNOWN_AFTER_APPLY]


@pytest.mark.parametrize(
    ("attr", "after", "unknown", "expected"),
    [
        pytest.param(
            "settings",
            {"tier": "b", "flags": None},
            {"tier": False, "flags": []},
            {"tier": "b", "flags": None},
            id="dict-key-null",
        ),
        pytest.param("disks", [None], [{"auto_delete": False}], [None], id="list-element-null"),
    ],
)
def test_container_marker_against_null_retains_the_null(
    attr: str, after: object, unknown: object, expected: object
) -> None:
    """A container marker carrying no unknown leaf must keep an explicit null.

    Dropping the position lost the fact that the plan nulls that attribute; in the
    list case the internal absence sentinel also reached `json.dumps` and aborted
    the whole report with an unhandled `TypeError`.
    """
    diff = calculate_diff({attr: "before"}, {attr: after}, {attr: unknown})
    assert diff[attr]["after"] == expected
    assert _format_report_value(diff[attr]["after"]) == json.dumps(expected)


def test_concrete_key_order_is_preserved_and_marker_only_keys_appended() -> None:
    """Resolution keeps the plan's key order so both cells of a row stay comparable.

    Only marker-only keys — which have no concrete counterpart to be ordered
    against — are appended, in sorted order, keeping the output deterministic. A
    marker-only key whose subtree holds no unknown leaf is not invented at all.
    """
    before = {"settings": {"zeta": 1, "alpha": 2}}
    after = {"settings": {"zeta": 9, "alpha": 2}}
    unknown = {"settings": {"zeta": False, "omega": True, "beta": True, "gamma": False}}

    diff = calculate_diff(before, after, unknown)

    assert _format_report_value(diff["settings"]["before"]) == '{"zeta": 1, "alpha": 2}'
    assert _format_report_value(diff["settings"]["after"]) == (
        '{"zeta": 9, "alpha": 2, "beta": "(known after apply) ⏳", "omega": "(known after apply) ⏳"}'
    )


def test_stdout_and_file_are_byte_identical_under_an_ascii_locale(tmp_path: Path) -> None:
    """Both destinations emit the same bytes even when the ambient locale is ASCII.

    An in-process runner cannot observe this: click pins UTF-8 on stdout while
    `Path.write_text` follows the ambient locale, so the two encoders agree only
    when the file path pins UTF-8 as well. The report is emoji-dense, so an
    unpinned file write aborts here rather than diverging silently.
    """
    plan_file = _FIXTURES / "stdout-json-list.json"
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")
    output_file = tmp_path / "report.md"
    # Drop any inherited PYTHONIOENCODING rather than popping it afterwards, which
    # would widen the mapping's value type past what `subprocess.run` accepts.
    env = {key: value for key, value in os.environ.items() if key != "PYTHONIOENCODING"}
    env |= {"LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}
    command = [sys.executable, "-m", "tf_peek.main", str(plan_file), "--config", str(config_file)]

    to_stdout = subprocess.run(command, env=env, capture_output=True, check=True)  # noqa: S603
    subprocess.run([*command, "--output", str(output_file)], env=env, capture_output=True, check=True)  # noqa: S603

    assert output_file.read_bytes() == to_stdout.stdout
    assert b"[true, false, null]" in to_stdout.stdout


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
