## Why

`make integration-tests` resolves to `echo "No op for now"` (`toolbox/mk/python-base-app.mk:41`),
yet `code-checks.yaml:162` runs it and reports a passing integration stage that verifies nothing.
This is why all six defects catalogued in `docs/studies/2026-08-15-capability-and-market-analysis.md`
reached v1.0: every one of them is invisible to unit tests of `calculate_diff` and `resolve_tier` in
isolation, and every one would have been caught by a single end-to-end test rendering a realistic plan.

This change builds the harness that proves P0 items 0.1–0.6. It is deliberately sequenced first
because without it, each subsequent fix is unverifiable and each regression is undetectable.

## What Changes

**Test plumbing — restore the seam `b9f555a` removed**

- `toolbox/mk/python-base-app.mk`: replace the hardcoded no-op recipe with
  `IT_TESTS_TARGETS ?= integration-tests-noop` dispatch, mirroring how `tests` already dispatches
  through `TESTS_TARGETS`. Keeps the no-op default for projects that have no integration tests,
  while making the target extensible again. Un-orphans the `IT_TESTS_TARGET` variable at line 3.
- `Makefile`: set `IT_TESTS_TARGETS ?= poe-integration-tests` alongside `APP_NAME`.
- `toolbox/mk/project.mk:19`: use `uv run $(UV_RUN_OPTIONS) $(UV_TASK_RUNNER) pytest:integration`.
  This is currently the only target in the repo that does not run under `--frozen`.
- `poe_tasks.toml`: add `"pytest:integration" = "pytest -m integration"`. `project.mk` has always
  called this task; it has never existed.
- `pytest.ini`: register the `integration` marker. `markers =` is empty and `--strict-markers` is
  on, so an unregistered marker is a hard error today.
- `tox.ini`: drop `allowlist_externals = bats` — a fossil of the pre-`b9f555a` bats harness.

**Integration test package**

- New `tests/integration/` package with a `conftest.py` that auto-applies the `integration` marker
  to everything collected beneath it, so the directory is the source of truth and no test can be
  added without the marker.
- Existing `tests/*.py` are **not** moved. Selection works identically without it, and the move
  would churn three files' blame inside a change that should read as pure addition.

**First end-to-end coverage**

- Committed fixture plan(s) exercising sensitive values, nested blocks, pipe/newline values, nested
  `after_unknown`, `replace_paths`, module addresses and `output_changes`.
- A golden-file assertion over the rendered Markdown.
- A determinism check running the CLI in repeated subprocesses under `PYTHONHASHSEED`.

Shipping at least one real integration test is **not optional**: `pytest -m integration` with zero
matching tests exits 5, so a wiring-only change would turn CI red.

## Capabilities

### New Capabilities

None. This change adds no user-facing behaviour — it is test tooling and build plumbing.
`.openspec.yaml` sets `skip_specs: true`.

### Modified Capabilities

None. The five existing specs (`critical-section-rendering`, `match-resolution`,
`resource-tier-config`, `silent-disclosure`, `tiered-summary-counts`) describe behaviour this change
observes but does not alter. The defect fixes that *do* change rendering behaviour are separate
changes (P0 0.1–0.5) and will carry their own spec deltas.

## Impact

**Files**: `Makefile`, `toolbox/mk/python-base-app.mk`, `toolbox/mk/project.mk`, `poe_tasks.toml`,
`pytest.ini`, `tox.ini`, new `tests/integration/**`.

**No `src/` changes.** `python -m tf_peek` currently fails (no `__main__.py`); the determinism test
uses `python -m tf_peek.main`, which works today. Adding a public module entrypoint is deferred to
P0 0.6 ("decide the CLI shape"), where it belongs alongside the `generate` subcommand question.

**Dependencies**: adds `syrupy` to the `dev` dependency group for golden snapshot management,
configured to write readable `.md` files rather than its default amber format — see
`design.md — Decision 6`.

**CI**: `make tests` continues to collect everything under `tests/`, so integration tests count
toward the Codecov number. `make integration-tests` runs them a second time (~3.5s) as a named gate
with clear failure attribution. This double-run is accepted deliberately.

**tox**: `commands = pytest` will now collect the integration suite across every environment in
`envlist`, the first coverage the CLI has had on non-default interpreters. Note that no CI workflow
invokes `tox`, so this remains local-only. `tox.ini` is also edited by the
`align-python-version-support` change; expect a trivial merge if they land close together.

**Downstream**: `toolbox/mk/*` originates from `looztra/toolbox` but is a fork, not a live mirror —
the files are git-tracked here and were last edited in place by `b9f555a`. The
`IT_TESTS_TARGETS` indirection is written to be upstreamable, but this change does not require it.
