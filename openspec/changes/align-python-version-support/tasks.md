## 1. Align the declarations

- [x] 1.1 `tox.ini`: change `envlist = py313,py312,py311,py310` to
      `envlist = py311,py312,py313,py314` — drops the environment that cannot resolve against
      `requires-python = ">=3.11"`, adds the interpreter the project is actually developed on
- [x] 1.2 `pyproject.toml`: replace the `Programming Language :: Python :: 3.10` classifier with
      `3.14`, leaving 3.11–3.13 in place, so the PyPI page matches `requires-python`
- [x] 1.3 `tox.ini`: the `setenv` block no longer contains `PYTHONPATH = {toxinidir}` — the
      `integration-test-harness` change already replaced it with `PYTHONHASHSEED = 0` (pins hash
      randomisation so the golden test is stable across process restarts; see that change's
      `design.md` for why). There is nothing left to remove here: `PYTHONPATH = {toxinidir}` was
      inert (`pytest.ini`'s `pythonpath = src` is what makes `tf_peek` importable), but
      `PYTHONHASHSEED = 0` is load-bearing and **must not** be deleted. Confirm the block still
      reads `setenv = \n    PYTHONHASHSEED = 0` and move on

## 2. Verify

- [x] 2.1 Run `make test-python-versions` and confirm all four environments pass — it currently
      aborts on the first one
- [x] 2.2 Confirm imports still resolve now that `setenv` no longer sets `PYTHONPATH`: `uv run tox
      -e py311` must still collect and pass the unit tests (35, plus whatever
      `integration-test-harness` has added by the time this lands)
- [x] 2.3 Run `make dist` and inspect the built wheel's metadata for the corrected
      `Programming Language` classifiers and unchanged `Requires-Python: >=3.11`
- [x] 2.4 Run `make lint` (taplo formats `pyproject.toml`; the classifier edit must survive it)

## 3. Do not include

Recorded so they are not picked up by accident — see `proposal.md — Deliberately not in scope`.

- [x] 3.1 Confirm no CI workflow was modified: wiring `tox` into CI is a separate decision about
      matrix cost, and this change leaves the multi-version claim untested by CI
- [x] 3.2 Confirm `pytest.ini` was not modified: tox continues to test the source tree rather than
      the installed distribution
- [x] 3.3 Confirm `allowlist_externals = python` was left unchanged in `tox.ini`: it was set by the
      `integration-test-harness` change, and editing it here would create a conflict
