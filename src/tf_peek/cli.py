"""Command-line interface for tf-peek."""

import json
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from pathlib import Path
from typing import Any

import typer
from pydantic import ValidationError

from .actions import Action
from .config import load_config
from .models import TerraformPlan
from .report import build_report_data, render_report

app = typer.Typer()


def _version_callback(ctx: typer.Context, show_version: bool) -> None:
    """Print the installed tf-peek version and exit, if the flag was passed.

    Registered as an eager typer callback so it runs — and can exit — before
    the required ``json_path`` argument is validated, matching the standard
    click/typer ``--version`` pattern.

    When the distribution's metadata is not discoverable (e.g. running from a
    source checkout outside an installed venv), the callback writes a
    one-line diagnostic to stderr and exits ``1`` rather than emitting a
    prose sentence on stdout with exit ``0`` — a wrapper script doing
    ``VER=$(tf-peek --version)`` should observe a non-zero exit and a
    parseable error, not silently capture prose as a version.
    """
    if ctx.resilient_parsing:
        return
    if show_version:
        try:
            version = _package_version("tf-peek")
        except PackageNotFoundError:
            typer.echo("tf-peek package metadata not found", err=True)
            raise typer.Exit(code=1) from None
        typer.echo(version)
        raise typer.Exit


def _gate_triggered(
    fail_on_critical: bool,
    fail_on_critical_on: list[Action],
    tiered_summary: dict[str, dict[str, int]],
    critical_to_render: dict[str, dict[str, list[dict[str, Any]]]],
) -> bool:
    """Decide whether the --fail-on-critical(-on) exit-code gate should fire.

    ``--fail-on-critical-on`` takes precedence when present: it evaluates against
    ``tiered_summary[action]["critical"]`` — the per-action count of ``tier == "critical"``
    resources, unfiltered by each rule's own ``critical_on`` — independent of whether
    ``--fail-on-critical`` was also passed. Otherwise ``--fail-on-critical`` mirrors exactly
    what the rendered 🚨 section (``critical_to_render``) shows. Neither flag passed never triggers.
    """
    if fail_on_critical_on:
        return any(tiered_summary[action.value]["critical"] > 0 for action in fail_on_critical_on)
    if fail_on_critical:
        return bool(critical_to_render)
    return False


def _read_plan_json(json_path: Path) -> str:
    """Return the plan JSON text for ``json_path``, reading from stdin when it is ``-``.

    Args:
        json_path: Path to the plan JSON file, or the literal ``Path("-")`` sentinel to read
            from standard input instead of a file.

    Returns:
        The plan JSON text, decoded as UTF-8 regardless of the ambient locale.
    """
    if json_path == Path("-"):
        return sys.stdin.buffer.read().decode("utf-8")
    return json_path.read_text(encoding="utf-8")


@app.command()
def generate(  # noqa: PLR0913, PLR0917 — typer CLI entrypoint, options map 1:1 to flags
    json_path: Path = typer.Argument(..., help="JSON plan file, or '-' to read from stdin"),
    config_file: Path | None = typer.Option(None, "--config", "-c"),
    output_file: Path | None = typer.Option(
        None, "--output", "-o", help="Output file for markdown report (default: stdout)"
    ),
    show_sensitive: bool = typer.Option(
        False, "--show-sensitive", help="Render sensitive attribute values instead of masking them"
    ),
    fail_on_critical: bool = typer.Option(
        False,
        "--fail-on-critical",
        help="Exit with status 3 if the rendered Critical Changes section is non-empty.",
    ),
    fail_on_critical_on: list[Action] = typer.Option(
        [],
        "--fail-on-critical-on",
        help=(
            "Exit with status 3 if a critical-tier resource has this action (repeatable). "
            "Enables the gate on its own and, when passed, takes precedence over "
            "--fail-on-critical. Evaluated independent of each rule's own critical_on."
        ),
    ),
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed tf-peek version and exit.",
    ),
) -> None:
    """Generate a markdown report from a terraform plan JSON."""
    config = load_config(config_file)

    try:
        plan_text = _read_plan_json(json_path)
        plan_data = json.loads(plan_text)
        plan = TerraformPlan(**plan_data)
    except OSError as exc:
        typer.echo(f"tf-peek: cannot read plan '{json_path}': {exc}", err=True)
        raise typer.Exit(code=1) from None
    except UnicodeDecodeError as exc:
        typer.echo(f"tf-peek: plan is not valid UTF-8: {exc}", err=True)
        raise typer.Exit(code=1) from None
    except json.JSONDecodeError as exc:
        typer.echo(f"tf-peek: plan is not valid JSON: {exc}", err=True)
        raise typer.Exit(code=1) from None
    except TypeError:
        typer.echo(f"tf-peek: plan JSON must be an object, got {type(plan_data).__name__}", err=True)
        raise typer.Exit(code=1) from None
    except ValidationError as exc:
        errors = exc.errors()
        first = errors[0]
        loc = ".".join(str(part) for part in first["loc"]) or "<root>"
        detail = f"{loc}: {first['msg']}"
        if len(errors) > 1:
            detail += f" (+{len(errors) - 1} more)"
        typer.echo(f"tf-peek: plan does not match the expected structure: {detail}", err=True)
        raise typer.Exit(code=1) from None

    data = build_report_data(plan, config, show_sensitive=show_sensitive)
    rendered_content = render_report(data)

    if output_file:
        if output_file.exists():
            typer.echo(f"Overwriting {output_file}")
        # Pin the encoding and line ending: click already forces UTF-8 with LF on
        # stdout, so both destinations must agree byte-for-byte regardless of the
        # ambient locale (an ASCII default would otherwise abort on the report's
        # emoji, and a Windows default would rewrite every newline).
        output_file.write_text(rendered_content, encoding="utf-8", newline="\n")
        typer.echo(f"Report written to {output_file}")
    else:
        # ``color=True`` stops click from stripping ANSI escapes when stdout is
        # not a TTY, so report content reaches stdout byte-identically to the
        # ``--output`` file.
        typer.echo(rendered_content, nl=False, color=True)

    if _gate_triggered(fail_on_critical, fail_on_critical_on, data.tiered_summary, data.critical_resources_by_action):
        raise typer.Exit(code=3)
