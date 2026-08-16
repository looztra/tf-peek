## 1. Align the declarations

- [ ] 1.1 `tox.ini`: change `envlist = py313,py312,py311,py310` to
      `envlist = py311,py312,py313,py314` — drops the environment that cannot resolve against
      `requires-python = ">=3.11"`, adds the interpreter the project is actually developed on
- [ ] 1.2 `pyproject.toml`: replace the `Programming Language :: Python :: 3.10` classifier with
      `3.14`, leaving 3.11–3.13 in place, so the PyPI page matches `requires-python`
- [ ] 1.3 `tox.ini`: delete the `setenv` block containing `PYTHONPATH = {toxinidir}`. It is inert —
      `pytest.ini`'s `pythonpath = src` is what makes `tf_peek` importable, and `{toxinidir}` only
      adds the repo root

## 2. Verify

- [ ] 2.1 Run `make test-python-versions` and confirm all four environments pass — it currently
      aborts on the first one
- [ ] 2.2 Confirm imports still resolve after removing `setenv`: `uv run tox -e py311` must still
      collect and pass the 35 unit tests
- [ ] 2.3 Run `make dist` and inspect the built wheel's metadata for the corrected
      `Programming Language` classifiers and unchanged `Requires-Python: >=3.11`
- [ ] 2.4 Run `make lint` (taplo formats `pyproject.toml`; the classifier edit must survive it)

## 3. Do not include

Recorded so they are not picked up by accident — see `proposal.md — Deliberately not in scope`.

- [ ] 3.1 Confirm no CI workflow was modified: wiring `tox` into CI is a separate decision about
      matrix cost, and this change leaves the multi-version claim untested by CI
- [ ] 3.2 Confirm `pytest.ini` was not modified: tox continues to test the source tree rather than
      the installed distribution
- [ ] 3.3 Confirm `allowlist_externals = bats` was left in `tox.ini`: it is removed by the
      `integration-test-harness` change (task 4.1), and editing it here would create a conflict
