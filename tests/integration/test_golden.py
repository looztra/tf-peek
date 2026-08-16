"""Golden end-to-end coverage: render the kitchen-sink plan and freeze the output.

This is the primary review artifact for the P0 defect fixes (0.1-0.5): each fix
produces a diff against `__snapshots__/test_golden/test_kitchen_sink_report.md`.
Regenerate with `uv run pytest -m integration --snapshot-update`.
"""

from pathlib import Path

from syrupy.assertion import SnapshotAssertion
from typer.testing import CliRunner

from tf_peek.main import app

_FIXTURES = Path(__file__).parent / "fixtures"


def test_kitchen_sink_report(tmp_path: Path, snapshot: SnapshotAssertion) -> None:
    """Render the kitchen-sink plan and compare it against the golden Markdown."""
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text("")
    output_file = tmp_path / "report.md"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            str(_FIXTURES / "kitchen-sink.json"),
            "--config",
            str(config_file),
            "--output",
            str(output_file),
        ],
    )
    assert result.exit_code == 0, result.output
    assert output_file.read_text() == snapshot
