"""Tests for the tf_peek CLI invocation surface."""

import json
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
