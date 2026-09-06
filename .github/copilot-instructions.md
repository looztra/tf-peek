---
This file is scoped to GitHub Copilot. `AGENTS.md` is the canonical, tool-agnostic instructions
file for this repo — read it first. `.agents/skills/` (mirrored into `.opencode/`, `.omp/`,
`.agent/`, `.claude/`, and `.github/skills/` via `skills-lock.json`) carries the detailed
per-topic conventions. This file adds only what is Copilot-specific: the maintenance matrix and
notes for the coding-agent environment.
---

# Copilot Instructions — tf-peek

## Language-specific conventions

Python only, managed with `uv`. Never invoke a bare `python`, `pytest`, or `ruff` — always
`uv run …` (or the `poe`/`make` wrappers, see `python-quality-gates` skill). Full type hints
required; checked with `ty` (`uv run poe ty:check`) and `pylint` (`uv run poe pylint`) in addition
to `ruff`.

## Framework patterns

- **CLI**: `typer` app object `tf_peek.cli:app`. User-facing output via `typer.echo(...)`,
  diagnostics via `typer.echo(..., err=True)`, exit codes via `raise typer.Exit(code=N)`. No
  `logging` module and no bare `print` in `src/`.
- **Models**: `pydantic` v2 `BaseModel`. Plan structure lives in `src/tf_peek/models.py`
  (`Change`, `ResourceChange`, `TerraformPlan`); configuration lives in `src/tf_peek/config.py`
  (`ResourceRule`, `PeekConfig`). Cross-field rules go in `@model_validator`, not `__init__`.
- **Templating**: report shape is the Jinja2 template `src/tf_peek/templates/report.md.j2`, fed by
  `src/tf_peek/report.py`. Never hand-format Markdown for the report elsewhere.
- **Action vocabulary**: `src/tf_peek/actions.py` defines `Action` (enum) and `ACTION_ORDER`; a
  test asserts their values stay in verbatim sync — update both together.

## Test conventions

- Runner is `pytest` (`uv run poe test`, coverage via `uv run poe test:cov`).
- Shared builders live in `tests/helpers.py` (`make_plan`, `rc_entry`, `run_generate`,
  `run_generate_raw`); use them instead of hand-rolling plan JSON fixtures.
- CLI behaviour is asserted through `typer.testing.CliRunner`, not subprocess calls.
- Everything under `tests/integration/` is auto-marked `integration` by the
  `pytest_collection_modifyitems` hook in `tests/integration/conftest.py`; run in isolation with
  `uv run poe pytest:integration`.
- The Markdown golden is `tests/integration/__snapshots__/test_golden/test_kitchen_sink_report.md`
  (syrupy). After an intentional rendering change, regenerate with
  `uv run poe pytest:integration --snapshot-update` and review the diff like code — never accept a
  snapshot update you haven't read.
- `tests/integration/test_defects.py` is the defect ledger for the issues catalogued in
  `docs/studies/2026-08-15-capability-and-market-analysis.md §4.1` (D1–D5 resolved, D6 out of
  scope). A failure there means a catalogued defect regressed — treat it as a release blocker, not
  a flaky test.

## Code style notes

- Formatting/lint: `ruff.toml` (extends `ruff_defaults.toml`) — `uv run poe ruff:fmt:check` /
  `ruff:lint`.
- Additional lint: `.pylintrc`.
- Type checking: `ty` config in `pyproject.toml`.
- Editor defaults: `.editorconfig`, enforced by `editorconfig-checker` in pre-commit.
- Markdown: `.markdownlint.yaml` / `.markdownlint-cli2.yaml`, enforced by the
  `markdownlint-cli2` pre-commit hook.
- Commits and PR titles: Conventional Commits with a **mandatory scope** — CI
  (`lint-pr-titles.yaml`) fails a title without one. See the `commit-and-pr-conventions` skill.

## Conventions mined from PR reviews

No repeatable review-comment patterns found: this is currently a solo-maintainer repo
(`looztra`) and dependency-update PRs are opened and auto-merged by `renovate[bot]` without human
review threads. Revisit this section as more contributors and reviewed PRs show up.

## Maintenance matrix

Changing one of these means checking the paired locations too — traced from actual imports and
cross-references, not guessed:

| Change this | Also check / update |
|---|---|
| `src/tf_peek/models.py` (plan schema: `Change`, `ResourceChange`, `TerraformPlan`) | `src/tf_peek/config.py` (`resolve_tier` reads `ResourceChange`), `tests/test_models.py`, `tests/helpers.py` builders, fixtures in `tests/integration/fixtures/*.json`, `docs/architecture/04-data-models.md` |
| `src/tf_peek/config.py` (`ResourceRule`, `PeekConfig`, `resolve_tier`, `load_config`) | `tests/test_config.py`, `docs/reference/configuration.md`, `docs/how-to/silence-noisy-resources.md`, `docs/how-to/flag-critical-resources.md`, example `peek_config.toml` snippets in `README.md` |
| `src/tf_peek/actions.py` (`Action`, `ACTION_ORDER`, `get_emoji`) | keep `Action` values and `ACTION_ORDER` in sync (a test enforces this), `tests/test_actions.py`, `--fail-on-critical-on` help text in `src/tf_peek/cli.py`, `docs/reference/cli.md` |
| `src/tf_peek/cli.py` (Typer app, flags, exit codes) | `docs/reference/cli.md`, usage examples in `README.md`, `tests/test_cli.py` |
| `src/tf_peek/report.py`, `diff.py`, or `causation.py` (report assembly, diff rendering, causation surfacing) | `src/tf_peek/templates/report.md.j2` in lockstep, regenerate the golden snapshot (`uv run poe pytest:integration --snapshot-update`) and review the diff, `tests/test_diff.py`, `tests/test_causation.py`, `tests/integration/test_causation.py` |
| `src/tf_peek/templates/report.md.j2` (report Markdown shape) | regenerate `tests/integration/__snapshots__/test_golden/test_kitchen_sink_report.md`, `docs/reference/*` if the visible shape changes |
| A catalogued defect in `tests/integration/test_defects.py` | `docs/studies/2026-08-15-capability-and-market-analysis.md §4.1` — the ledger and the study must stay in sync |
| `.mise.toml` / `.python-version` / Python or `uv` version | `.github/workflows/code-checks.yaml`, `.github/workflows/copilot-setup-steps.yml` (most bumps arrive via Renovate already) |
| `poe_tasks.toml` / `Makefile` verification commands | `AGENTS.md` non-negotiables, `.agents/skills/python-quality-gates/SKILL.md` (and its mirrors) |
| `mkdocs.yml` nav / new page under `docs/` | doc links table in `README.md`, `docs/index.md` |

## Copilot coding-agent environment

The bootstrap steps for Copilot's cloud environment live in
`.github/workflows/copilot-setup-steps.yml`, mirroring the `pre-commit`/`python-checks` setup in
`.github/workflows/code-checks.yaml`. Keep them in sync when the setup sequence changes there.
