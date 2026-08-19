"""Tests for the tf_peek CLI invocation surface."""

import json
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from tests.helpers import make_plan, rc_entry
from tf_peek.cli import _version_callback, app

# ---------------------------------------------------------------------------
# Integration: output destination
# ---------------------------------------------------------------------------


def test_generate_warns_when_overwriting_existing_output_file(tmp_path: Path) -> None:
    """Running generate twice against the same --output path prints an overwrite notice."""
    plan = make_plan([rc_entry("google_storage_bucket", "b1", ["create"], after={"name": "b1"})])
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
    plan = make_plan([rc_entry("google_storage_bucket", "b1", ["create"], after={"name": "b1"})])
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
    monkeypatch.setattr("tf_peek.cli._package_version", lambda _name: "9.9.9")
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "9.9.9"


def test_version_short_flag_behaves_like_long_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """-V behaves identically to --version."""
    monkeypatch.setattr("tf_peek.cli._package_version", lambda _name: "9.9.9")
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

    monkeypatch.setattr("tf_peek.cli._package_version", _raise_not_found)
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
    plan_file.write_text(json.dumps(make_plan([])))

    runner = CliRunner()
    result = runner.invoke(app, ["generate", str(plan_file)])
    assert result.exit_code == 2, result.output  # noqa: PLR2004 — click "usage error" exit code


# ---------------------------------------------------------------------------
# Integration: stdin plan source
# ---------------------------------------------------------------------------


def test_generate_reads_plan_from_stdin(tmp_path: Path) -> None:
    """`tf-peek -` reads the plan JSON from stdin and renders the same report as a file path."""
    plan = make_plan([rc_entry("google_storage_bucket", "b1", ["create"], after={"name": "b1"})])
    plan_json = json.dumps(plan)
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")

    runner = CliRunner()
    stdin_result = runner.invoke(app, ["-", "--config", str(config_file)], input=plan_json)
    assert stdin_result.exit_code == 0, stdin_result.output

    plan_file = tmp_path / "plan.json"
    plan_file.write_text(plan_json)
    file_result = runner.invoke(app, [str(plan_file), "--config", str(config_file)])
    assert file_result.exit_code == 0, file_result.output

    assert stdin_result.output == file_result.output


def test_module_invocation_reads_plan_from_stdin(tmp_path: Path) -> None:
    """`python -m tf_peek -` behaves identically to `tf-peek -`.

    Covers the "Module invocation supports stdin identically" scenario as a real subprocess
    invocation of the module entrypoint, rather than only the in-process ``CliRunner`` coverage
    above — ``__main__.py`` delegates straight to the same Typer ``app`` (see
    ``test_module_entrypoint_invokes_cli_app``), so this exercises the identical stdin code path
    through the actual `-m` entrypoint.
    """
    plan = make_plan([rc_entry("google_storage_bucket", "b1", ["create"], after={"name": "b1"})])
    plan_json = json.dumps(plan)
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "tf_peek", "-", "--config", str(config_file)],
        input=plan_json,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "google_storage_bucket.b1" in result.stdout


def test_generate_without_json_path_is_a_usage_error() -> None:
    """Omitting JSON_PATH entirely stays a usage error (exit 2) and does not implicitly read stdin."""
    runner = CliRunner()
    result = runner.invoke(app, [])
    assert result.exit_code == 2, result.output  # noqa: PLR2004 — click "usage error" exit code


# ---------------------------------------------------------------------------
# Integration: plan-loading failure diagnostics
# ---------------------------------------------------------------------------


def test_generate_nonexistent_file_path_exits_one_with_clean_diagnostic(tmp_path: Path) -> None:
    """A nonexistent `JSON_PATH` file exits 1 with a one-line diagnostic, not an uncaught traceback.

    File-only: stdin has no equivalent "missing" case (there is nothing to open by path).
    """
    missing_file = tmp_path / "missing.json"
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")

    runner = CliRunner()
    result = runner.invoke(app, [str(missing_file), "--config", str(config_file)])

    assert result.exit_code == 1, result.output
    assert "cannot read plan" in result.output
    assert "Traceback" not in result.output


def test_generate_unreadable_plan_path_exits_one_with_clean_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A read failure after argument parsing exits 1 instead of becoming a usage error."""
    plan_file = tmp_path / "plan.json"
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")

    def raise_permission_error(*_args: object, **_kwargs: object) -> str:
        raise PermissionError

    monkeypatch.setattr(Path, "read_text", raise_permission_error)
    result = CliRunner().invoke(app, [str(plan_file), "--config", str(config_file)])

    assert result.exit_code == 1, result.output
    assert "cannot read plan" in result.output
    assert "Traceback" not in result.output


def test_generate_reads_dot_dash_as_a_file_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`./-` opens a file named `-` instead of selecting the stdin sentinel."""
    plan = make_plan([rc_entry("google_storage_bucket", "b1", ["create"], after={"name": "b1"})])
    dash_file = tmp_path / "-"
    dash_file.write_text(json.dumps(plan))
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["./-", "--config", str(config_file)])

    assert result.exit_code == 0, result.output
    assert "google_storage_bucket.b1" in result.output


@pytest.mark.parametrize(
    ("content", "expected_snippet"),
    [
        pytest.param("{not valid json", "not valid JSON", id="malformed-json"),
        pytest.param("", "not valid JSON", id="empty-input"),
        pytest.param("[]", "must be an object", id="non-object-json-array"),
        pytest.param('"a string"', "must be an object", id="non-object-json-string"),
        pytest.param(
            json.dumps({"resource_changes": "not-a-list"}),
            "does not match the expected structure",
            id="wrong-resource-changes-type",
        ),
    ],
)
@pytest.mark.parametrize("source", ["file", "stdin"])
def test_generate_malformed_or_invalid_plan_exits_one_with_clean_diagnostic(
    source: str,
    content: str,
    expected_snippet: str,
    tmp_path: Path,
) -> None:
    """Each malformed/invalid-plan failure mode exits 1 with a clean diagnostic, no traceback.

    Identically whether the plan comes from a file path or stdin.
    """
    runner = CliRunner()
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")
    if source == "file":
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(content)
        result = runner.invoke(app, [str(plan_file), "--config", str(config_file)])
    else:
        result = runner.invoke(app, ["-", "--config", str(config_file)], input=content)

    assert result.exit_code == 1, result.output
    assert expected_snippet in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("source", ["file", "stdin"])
def test_generate_multi_error_plan_reports_remaining_validation_errors(source: str, tmp_path: Path) -> None:
    """A multi-error plan reports the first validation error plus its remaining count."""
    content = json.dumps({"resource_changes": [{}]})
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")
    if source == "file":
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(content)
        result = CliRunner().invoke(app, [str(plan_file), "--config", str(config_file)])
    else:
        result = CliRunner().invoke(app, ["-", "--config", str(config_file)], input=content)

    assert result.exit_code == 1, result.output
    assert "does not match the expected structure" in result.output
    assert "(+" in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("source", ["file", "stdin"])
def test_generate_invalid_utf8_plan_exits_one_with_clean_diagnostic(source: str, tmp_path: Path) -> None:
    """Undecodable plan bytes exit 1 with the specified diagnostic for either input source."""
    content = b"\xff\xfe"
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")
    runner = CliRunner()
    if source == "file":
        plan_file = tmp_path / "plan.json"
        plan_file.write_bytes(content)
        result = runner.invoke(app, [str(plan_file), "--config", str(config_file)])
    else:
        result = runner.invoke(app, ["-", "--config", str(config_file)], input=content)

    assert result.exit_code == 1, result.output
    assert "not valid UTF-8" in result.output
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# Integration: locale-independent decoding
# ---------------------------------------------------------------------------


def test_plan_decodes_as_utf8_under_non_utf8_locale(tmp_path: Path) -> None:
    """Non-ASCII plan content decodes correctly under a non-UTF-8 process locale (e.g. `LANG=C`).

    Covers both file and stdin sources. Locale-derived stream encodings are resolved once at
    interpreter startup, so this runs the CLI in a fresh subprocess with `LANG`/`LC_ALL` forced
    to the legacy "C" locale — and PEP 538/540 auto-coercion/UTF-8-mode disabled — rather than
    monkeypatching the current process's already-initialized environment, which would not
    observably change stream encodings.
    """
    plan = make_plan([rc_entry("google_storage_bucket", "b1", ["create"], after={"name": "café-\u00e9toile"})])
    plan_json = json.dumps(plan, ensure_ascii=False)

    env = {key: value for key, value in os.environ.items() if key != "PYTHONIOENCODING"}
    env.update(LANG="C", LC_ALL="C", PYTHONCOERCECLOCALE="0", PYTHONUTF8="0")

    plan_file = tmp_path / "plan.json"
    plan_file.write_bytes(plan_json.encode("utf-8"))
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")

    file_result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "tf_peek", str(plan_file), "--config", str(config_file)],
        env=env,
        capture_output=True,
        check=False,
    )
    assert file_result.returncode == 0, file_result.stderr.decode("utf-8", errors="replace")
    assert "café".encode() in file_result.stdout

    stdin_result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "tf_peek", "-", "--config", str(config_file)],
        input=plan_json.encode("utf-8"),
        env=env,
        capture_output=True,
        check=False,
    )
    assert stdin_result.returncode == 0, stdin_result.stderr.decode("utf-8", errors="replace")
    assert "café".encode() in stdin_result.stdout
