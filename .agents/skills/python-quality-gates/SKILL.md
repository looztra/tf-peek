---
name: python-quality-gates
description: Run and interpret this repository family's mandatory checks. Use before handing back any change to execute style, lint, type-check, tests and pre-commit hooks in the expected order via uv and poe.
---

Use this skill for the final verification pass on any change.

## Required commands

Run from the repository root, always through `uv` (never a bare `python`, `pytest`, `ruff`, or
`pylint`):

1. `uv run poe style` — formatting **and** import sorting (`ruff format`, then
   `ruff check --select I --fix`). This is the formatting gate; `ruff:fmt:run` alone is not enough.
2. `uv run poe lint:all` — `ruff format --check`, `ruff check`, `pylint`, `ty check`.
3. `uv run poe test` — the full `pytest` run.

Conditional:

- Coverage or CI parity: `uv run poe pytest:cov` (`--cov src --cov-branch`, writes the JUnit XML).
- A marked subset only (e.g. an end-to-end suite): the matching `poe` task, e.g.
  `uv run poe pytest:integration`.
- Markdown, YAML, TOML or shell touched: `uv run pre-commit run --all-files`, or one hook, e.g.
  `uv run pre-commit run --all-files markdownlint-cli2`.
- Docs sources or `mkdocs.yml` touched: `make build-docs`.

Confirm the task names for the current repository with `uv run poe --help` or by reading
`poe_tasks.toml`; skip a conditional command only when the task genuinely does not exist. `make`
wraps the same tasks (`make lint`, `make test`, `make integration-tests`, `make dist`) and is what CI
invokes.

## Execution rules

1. Run in the order above unless the task says otherwise: styling first keeps step 2 from failing on
   a pure formatting diff.
2. If `poe lint:all` fails on `ruff format --check` right after `poe style`, re-run `poe style` once
   (import sorting can reflow a line) and only then investigate.
3. On any failure, stop, fix the cause, then re-run that step and every later step.
4. Fix findings; do not silence them. A suppression needs an inline rule id plus a reason and must be
   the exception.
5. Ruff owns line length and most pylint rules (`.pylintrc` disables them on purpose). Never edit
   `ruff_defaults.toml`; add project ignores to `ruff.toml`.
6. `poe lint:all` does not include `pyright`; `uv run poe pyright` exists as an opt-in extra.
7. When you cannot fix something, report the file, the rule id or test name, and the failing output.

## Auto-fix helpers

- `uv run poe ruff:lint:fix` — `ruff check --fix`.
- `uv run poe ruff:isort` — import sorting only.
- `uv run taplo format --config .taplo.toml` — TOML formatting (also a pre-commit hook).
