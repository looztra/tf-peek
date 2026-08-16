## Why

`make test-python-versions` is broken. `tox.ini` lists `py310` in `envlist` while
`pyproject.toml` sets `requires-python = ">=3.11"`, so the run aborts before testing anything:

```console
$ uv run tox -e py310 --notest
error: The requested interpreter resolved to Python 3.10.20, which is incompatible
       with the project's Python requirement: `>=3.11` (from `project.requires-python`)
py310: FAIL code 2
```

Underneath that, five sources declare the supported Python versions and no two agree:

| Source | Claims |
| :--- | :--- |
| `.python-version`, the local `.venv`, and CI (`uv python install`) | **3.14** |
| `pyproject.toml` `requires-python` | `>=3.11` |
| `pyproject.toml` classifiers | 3.10, 3.11, 3.12, 3.13 |
| `tox.ini` `envlist` | py310, py311, py312, py313 |

3.14 is the interpreter every developer and every CI job actually runs on, and it is advertised
nowhere. 3.10 is advertised on PyPI and tested by tox, and is supported nowhere. The classifiers are
what render on the PyPI project page, so the wrong ones are publicly visible.

## What Changes

`requires-python = ">=3.11"` is treated as the source of truth; everything else is aligned to it,
with 3.14 added because it is what the project is developed and shipped against.

- `tox.ini`: `envlist = py311,py312,py313,py314` — drops the failing `py310`, adds `py314`.
- `pyproject.toml`: classifiers become 3.11, 3.12, 3.13, 3.14.
- `tox.ini`: remove the `setenv PYTHONPATH = {toxinidir}` block. It is inert — `pytest.ini` already
  sets `pythonpath = src`, which is what makes `tf_peek` importable; `{toxinidir}` only adds the
  repo root, which nothing needs.

All four target interpreters were verified to pass the existing 35 tests before this change was
written:

```console
py311: OK  (Python 3.11.15, 35 passed)
py312: OK  (Python 3.12.13, 35 passed)
py313: OK  (Python 3.13.14, 35 passed)
py314: OK  (Python 3.14.7,  35 passed)
```

**Deliberately not in scope:**

- **Wiring tox into CI.** No workflow invokes `tox` or `make test-python-versions`, so the
  multi-version claim stays untested by CI after this change. Fixing that is a separate decision
  about CI matrix cost.
- **Making tox test the installed distribution.** `pytest.ini`'s `pythonpath = src` shadows the
  installed package, so tox validates the source tree across interpreters rather than the wheel.
  That is adequate for catching syntax and stdlib incompatibilities, and `make dist` plus the
  TestPyPI publish already exercise packaging. Changing it would require decoupling `pythonpath`
  from the main pytest run for a benefit this change does not need.
- `tox.ini`'s `allowlist_externals = bats` — removed by the `integration-test-harness` change
  (task 4.1), deliberately left alone here to avoid a conflicting edit to the same file.

## Capabilities

### New Capabilities

None. This change touches build configuration and package metadata only.
`.openspec.yaml` sets `skip_specs: true`.

### Modified Capabilities

None. No runtime behaviour changes and `requires-python` is unchanged, so no currently-supported
installation stops working.

## Impact

**Files**: `tox.ini`, `pyproject.toml`.

**PyPI**: the classifier list on the project page changes. Dropping the 3.10 classifier is a
correction, not a removal of support — `requires-python = ">=3.11"` already prevented 3.10 installs,
so no working install breaks. Adding 3.14 makes the page reflect reality.

**Contributors**: `make test-python-versions` starts working. It currently fails on the first
environment, which likely means it is not being run at all.

**Interaction with `integration-test-harness`**: that change makes `tox` collect an integration
suite for the first time, adding ~3.5 s per environment across four interpreters instead of three.
Both changes edit `tox.ini`; if they land close together, expect a trivial merge.
