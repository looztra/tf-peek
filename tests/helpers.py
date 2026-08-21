"""Shared test builders for constructing plans, resource changes, and CLI invocations."""

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner, Result

from tf_peek.cli import app


def make_plan(resource_changes: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a minimal Terraform plan dict."""
    return {"resource_changes": resource_changes}


def rc_entry(  # noqa: PLR0913, PLR0917
    rtype: str,
    name: str,
    actions: list[str],
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    module: str = "root",
    replace_paths: list[list[Any]] | None = None,
    action_reason: str | None = None,
) -> dict[str, Any]:
    """Build a minimal resource_change entry."""
    address_prefix = f"module.{module}." if module != "root" else ""
    entry: dict[str, Any] = {
        "address": f"{address_prefix}{rtype}.{name}",
        "module_address": module,
        "type": rtype,
        "name": name,
        "change": {
            "actions": actions,
            "before": before,
            "after": after,
            "after_unknown": None,
            "replace_paths": replace_paths or [],
        },
    }
    if action_reason is not None:
        entry["action_reason"] = action_reason
    return entry


def run_generate(plan: dict[str, Any], config_content: str, tmp_path: Path) -> str:
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


def run_generate_raw(plan: dict[str, Any], config_content: str, tmp_path: Path, extra_args: list[str]) -> Result:
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
