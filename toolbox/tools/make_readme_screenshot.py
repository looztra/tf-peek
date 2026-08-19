"""Build the standalone before/after HTML used for the README screenshot.

Usage:
    uv run python toolbox/tools/make_readme_screenshot.py BEFORE_MD AFTER_MD OUT_HTML

Both panels are clipped to the same fixed-height window, so the screenshot is reproducible and shows
only what a reviewer sees before scrolling. See CONTRIBUTING.md for the full recipe.
"""  # noqa: INP001 — a one-off maintenance script, deliberately not a package

import argparse
import re
from pathlib import Path

import markdown

_CSS_PATH = Path(__file__).with_name("report-screenshot.css")

_BEFORE_CAPTION = "Without <b>peek_config.toml</b> — every change looks the same"
_AFTER_CAPTION = "With <b>peek_config.toml</b> — 🚨 <b>critical first, noise counted</b>"

_COLOR_HACK = re.compile(r"\$\{\\color\{(?P<color>red|orange)\}(?P<value>[^}]*)\}\$")


def render_report(md_text: str) -> str:
    r"""Render a tf-peek Markdown report to an HTML fragment.

    Args:
        md_text: Report Markdown as produced by ``tf-peek``.

    Returns:
        The HTML fragment, with ``<details>`` blocks forced open (a still image cannot expand them)
        and the report's ``${\color{...}}`` math hack replaced by the coloured text GitHub shows.
    """
    opened = md_text.replace("<details>", '<details open markdown="1">')
    coloured = _COLOR_HACK.sub(r'<b style="color:\g<color>">\g<value></b>', opened)
    return markdown.markdown(coloured, extensions=["tables", "md_in_html", "sane_lists"])


def _panel(caption: str, body_html: str) -> str:
    """Wrap a rendered report in a captioned, clipped panel."""
    return (
        f'<div class="panel"><div class="cap">{caption}</div>'
        f'<div class="body"><div class="md">{body_html}</div><div class="fade"></div></div></div>'
    )


def build_html(before_md: str, after_md: str) -> str:
    """Build the complete two-panel HTML document.

    Args:
        before_md: Report rendered without a tier configuration.
        after_md: Report rendered with the repository's ``config.toml``.

    Returns:
        A self-contained HTML document: inline CSS, no external assets.
    """
    css = _CSS_PATH.read_text(encoding="utf-8")
    panels = _panel(_BEFORE_CAPTION, render_report(before_md)) + _panel(_AFTER_CAPTION, render_report(after_md))
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<style>{css}</style></head><body><div class='wrap'>{panels}</div></body></html>"
    )


def main() -> None:
    """Parse arguments and write the screenshot HTML."""
    parser = argparse.ArgumentParser(description="Build the README before/after screenshot HTML.")
    parser.add_argument("before_md", type=Path, help="report rendered with an empty config")
    parser.add_argument("after_md", type=Path, help="report rendered with config.toml")
    parser.add_argument("out_html", type=Path, help="destination HTML file")
    args = parser.parse_args()
    args.out_html.parent.mkdir(parents=True, exist_ok=True)
    args.out_html.write_text(
        build_html(args.before_md.read_text(encoding="utf-8"), args.after_md.read_text(encoding="utf-8")),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
