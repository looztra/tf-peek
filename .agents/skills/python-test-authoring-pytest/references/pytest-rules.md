# Pytest rules

## Placement and naming

- All tests under `tests/`; `pytest.ini` sets `testpaths`, `pythonpath = src` and
  `addopts = --strict-markers --strict-config -ra`.
- One test module per production module: `test_<module>.py`.
- Sub-suites (e.g. an end-to-end suite) get their own directory with an `__init__.py` and a
  `conftest.py`.
- Shared builders live in one helper module inside `tests/`; do not create parallel helper modules.

## Framework and fixtures

- `pytest` only; do not add `unittest`-style tests. Leave existing ones alone unless asked.
- Shared fixtures in `conftest.py`, closest to the tests that use them.
- `@pytest.fixture` bare when argument-less; `@pytest.fixture(name="…")` when the fixture function
  name would shadow a parameter name. Overriding a built-in/plugin fixture with the same name needs
  `# pylint: disable=redefined-outer-name`.

## Parametrization

- Tuple syntax for parameter names, including single-parameter cases.
- `pytest.param(...)` entries with an explicit `id=` so failures name themselves; add `marks=` for
  `xfail`/`skipif` cases.
- `xfail(strict=True)` for catalogued defects; delete the marker when the defect is fixed — strict
  mode fails CI on an unexpected pass.

## Assertions

- Include the observed output in the assertion message for process-like assertions:
  `assert result.exit_code == 0, result.output`.
- `pytest.raises(Error, match="…")` for exception validation.
- `pytest-unordered` (when the project depends on it) is useful for order-insensitive collection
  comparisons.
- `HTTPStatus` from `http` rather than bare status integers when asserting HTTP codes.

## Markers and suites

- Declare every marker in `pytest.ini`; `--strict-markers` rejects undeclared ones.
- A directory-scoped marker is best applied automatically by a `pytest_collection_modifyitems` hook
  in that directory's `conftest.py`, so a new test cannot forget it.
- Run a marked subset with `pytest -m <marker>` (often wired as a `poe` task).

## Snapshots and goldens

- Committed golden/snapshot files are the review artifact: keep them in a readable format and review
  their diff like source code.
- Regenerate only after confirming the change is intended, using the project's snapshot-update
  command (e.g. a `poe` task plus `--snapshot-update`), then re-read the diff.
- Never hand-edit a generated golden.

## Ruff in tests

- `ruff_defaults.toml` per-file ignores for tests: `INP001`, `S101`, `D100`, `D104`. Everything else
  still applies — test functions need docstrings, magic numbers still trip `PLR2004` (name a
  constant or add `# noqa: PLR2004 — reason`), imports stay at top level (`PLC0415`).
- Prefer a `faker`-based fixture (where `faker` is available) instead of hardcoding
  credential-looking literals (`S105`/`S106`).

## Coverage expectations

- The coverage task runs `--cov src --cov-branch` and writes a JUnit XML under `generated/`; CI
  typically uploads both to the project's coverage service (Codecov in this template family).
- Every new branch in `src/` needs at least one test that fails without the change.
- Cover empty input, invalid input types, and hostile/edge inputs, not only the happy path.
