## 1. Plumbing

Goal: `make integration-tests` runs real pytest and can fail CI. Must land green — see
`design.md — Context` on the exit-5 constraint.

- [x] 1.1 Register the `integration` marker in `pytest.ini` under `markers =` (empty today, and
      `--strict-markers` makes an unregistered marker a hard error)
- [x] 1.2 Add `"pytest:integration" = "pytest -m integration"` to `poe_tasks.toml`
      (`toolbox/mk/project.mk:19` has always called this task; it has never existed)
- [x] 1.3 Change `toolbox/mk/project.mk:19` to
      `@uv run $(UV_RUN_OPTIONS) $(UV_TASK_RUNNER) pytest:integration` — currently the only target
      in the repo not running under `--frozen`
- [x] 1.4 Replace the hardcoded no-op recipe in `toolbox/mk/python-base-app.mk` with
      `IT_TESTS_TARGETS ?= integration-tests-noop` plus `$(MAKE) $(IT_TESTS_TARGETS)` dispatch, and
      add the `integration-tests-noop` target; keep `integration-test` as its wrapper
- [x] 1.5 Set `IT_TESTS_TARGETS ?= poe-integration-tests` in `Makefile` alongside `APP_NAME`
- [x] 1.6 Create `tests/integration/__init__.py` and `tests/integration/conftest.py`, the latter
      auto-applying the `integration` marker via `pytest_collection_modifyitems`
- [x] 1.7 Add one trivial passing integration test so the marker matches and `pytest -m integration`
      does not exit 5
- [x] 1.8 Verify `make integration-tests` passes, `make tests` still collects all tests, and
      `uv run pytest -m "not integration"` selects only the original 35

## 2. Golden harness

- [x] 2.1 Add `syrupy` to the `dev` dependency group in `pyproject.toml`; refresh `uv.lock`
- [x] 2.2 Configure a single-file **text** snapshot extension so goldens are written as readable
      `.md`, not syrupy's default `.ambr` (see `design.md — Decision 6`); confirm the file lands
      where a PR diff will show it
- [x] 2.3 Write `tests/integration/fixtures/kitchen-sink.json` covering sensitive values, a nested
      block, a value containing `|` and a newline, nested `after_unknown`, `replace_paths`,
      `module_address`, and `output_changes`
- [x] 2.4 Cross-check the fixture against the shape rules in `design.md — Decision 8`:
      `before_sensitive`/`after_sensitive` may be `bool`/`dict`/`list`; `replace_paths` mixes string
      keys and integer indices; `after_unknown` mirrors the value shape
- [x] 2.5 Add the golden test rendering `kitchen-sink.json` through `CliRunner` and asserting
      against the snapshot; generate the initial golden with `--snapshot-update`
- [x] 2.6 Read the generated golden and confirm it reproduces the defects documented in
      `docs/studies/2026-08-15-capability-and-market-analysis.md §9` — a golden that looks correct
      means the fixture is not exercising what it should
- [x] 2.7 Replace the placeholder test from 1.7

## 3. Defect ledger

Each entry is one `@pytest.mark.xfail(strict=True, reason="D<n>: …")` assertion that fails for a
single nameable reason. `strict=True` is required: it makes CI fail when a fix lands without the
marker being removed.

- [x] 3.1 Add focused fixtures `sensitive.json`, `hostile-strings.json`, `nested-unknown.json`
- [x] 3.2 D1 — assert no sensitive value appears in the rendered report
- [x] 3.3 D3 — assert every table row in the report has a consistent column count and no cell
      contains a raw newline
- [x] 3.4 D4 — assert rendered values are JSON (no `'`-quoted keys, no `True`/`None`)
- [x] 3.5 D5 — assert a nested `after_unknown` surfaces in the report
- [x] 3.6 D2 — subprocess determinism: run `[sys.executable, "-m", "tf_peek.main", …]` five times
      under differing `PYTHONHASHSEED` and assert byte-identical output. This one is xfail from the
      start rather than after a snapshot
- [x] 3.7 Add a fast in-process companion assertion that `calculate_diff` returns sorted keys —
      the subprocess test proves the property, this one locates the break
- [x] 3.8 Confirm every ledger entry fails for its own stated reason and not incidentally

## 4. Cleanup and verification

- [x] 4.1 Remove `allowlist_externals = bats` from `tox.ini` (fossil of the pre-`b9f555a` harness)
- [x] 4.2 Run `uv run tox` and confirm the integration suite passes on py311–py313; budget ~3.5 s
      per environment
- [x] 4.3 Run `make lint` — `ruff_defaults.toml`'s `**/tests/**/*` ignores are recursive and should
      already cover `tests/integration/`; `pylint tf_peek tests` recurses and needs the
      `__init__.py` from 1.6
- [x] 4.4 Confirm the Codecov number rises rather than falls (integration tests are inside the
      `pytest:cov` collection by design — see `design.md — Decision 3`)
- [x] 4.5 Update `docs/` or `CONTRIBUTING.md` with how to run and update goldens
      (`make integration-tests`, `--snapshot-update`)
