## Context

See `proposal.md — Why`. The constraints that shape the approach:

- **`toolbox/mk/*` is a fork, not a live mirror.** `remote-mk.mk` declares
  `REMOTE_MK_REPO ?= looztra/toolbox`, but its fetch writes to `LOCAL_MK_CACHE = generated/mk`
  (gitignored) while `Makefile` includes from `LOCAL_MK_ROOT = toolbox/mk` (git-tracked). Nothing
  defines `MK_GIT_REF` or any `MK_<NAME>_SHA256`, so the fetch machinery is dormant. `b9f555a`
  edited `python-base-app.mk` in place. Editing these files locally is established practice.
- **`pytest -m integration` with zero matching tests exits 5.** Verified. The wiring cannot ship
  without at least one real integration test or CI goes red.
- **`pytest.ini` has `--strict-markers` with an empty `markers =`.** Any marker is a hard error
  until registered.
- **`testpaths = tests`**, and `make tests` → `tests-uv-default` → `tests-with-coverage` →
  `poe pytest:cov` → bare `pytest --cov src`. Anything under `tests/` is collected by the coverage
  run whether or not the integration gate also runs it.
- **`python -m tf_peek` fails today** — there is no `src/tf_peek/__main__.py`.
  `python -m tf_peek.main` works.
- **Measured costs**: cold `tf-peek` subprocess ≈ 256 ms; current unit suite 0.37 s.
  Projected integration suite ≈ 3.5 s.

## Goals / Non-Goals

**Goals:**

- A single command (`make integration-tests`) that runs end-to-end tests and can fail CI.
- An executable, self-maintaining ledger of the six catalogued defects, so each P0 fix has an
  unambiguous definition of done.
- Golden diffs that are the primary review artifact for P0 0.1–0.5.
- Restore build plumbing that stays upstreamable to `looztra/toolbox`.

**Non-Goals:**

- **No `src/` changes.** In particular no `__main__.py` — see Decision 4.
- **No documented-invocation tests (D6).** Deferred to P0 0.6. Asserting that the commands in the
  README exit 0 is premature while the CLI shape is still undecided; the test and the decision
  should land together.
- **No defect fixes.** This change makes D1–D5 *visible and failing*; it fixes none of them.
- **No semantic/structured diffing of the golden.** Plain text comparison only.

## Decisions

### 1. Restore `IT_TESTS_TARGETS` dispatch in the fork

`python-base-app.mk` gets the same indirection `tests` already has:

```make
IT_TESTS_TARGETS ?= integration-tests-noop
integration-tests:
	@$(MAKE) --no-print-directory $(IT_TESTS_TARGETS)
```

with `IT_TESTS_TARGETS ?= poe-integration-tests` set in `Makefile` next to `APP_NAME`.

This reframes `b9f555a` rather than reverting it: wanting a no-op default was right, hardcoding it
was not. Projects with no integration tests keep passing; this one opts in. The shape mirrors
`TESTS_TARGETS ?= tests-uv-default`, so it is upstreamable as-is.

*Alternatives:* redefine `integration-tests:` in `project.mk` — works (last include wins) but GNU
make prints `warning: overriding recipe for target` on every invocation. Point CI at
`make poe-integration-tests` — two-line CI edit, but abandons the standard target name and leaves
`IT_TESTS_TARGET` orphaned.

### 2. Directory layout as source of truth, marker applied automatically

`tests/integration/conftest.py` applies the `integration` marker to everything collected beneath it
via `pytest_collection_modifyitems`. The filesystem decides; no test can be added to the directory
and miss the marker.

Existing `tests/*.py` are **not** moved into `tests/unit/`. Selection works identically without it
(`-m "not integration"` or a path), `ruff_defaults.toml`'s `**/tests/*` `INP001` exemption is
non-recursive so a move would need new `__init__.py` files, and it churns three files' blame inside
a change that should read as pure addition. The move stays available later as a standalone tidy-up.

*Alternatives:* decorate each test (rots the moment someone forgets); directory-only selection
(loses the `-m` selector that `poe pytest:integration` uses).

### 3. `pytest:cov` keeps collecting everything; the double-run is accepted

`make tests` covers unit + integration and owns the Codecov number. `make integration-tests` runs
the integration suite a second time as a named gate with clear failure attribution.

The ~3.5 s of duplicated work is noise, and the alternative is worse: deselecting integration from
the coverage run makes the golden harness — which exercises the entire render path — contribute
nothing to coverage, and the PR that adds it would show up as a coverage regression.

### 4. Two different subprocess targets, and no `__main__.py`

| Test | Target | Reason |
| :--- | :--- | :--- |
| Determinism | `[sys.executable, "-m", "tf_peek.main", ...]` | needs only a fresh interpreter; must not depend on console-script installation |
| Doc invocations (deferred) | `tf-peek` from `PATH` | the point is the literal command a user copies |

`python -m tf_peek` would be nicer, but adding `__main__.py` is a `src/` change that introduces a
new public invocation path — i.e. user-facing behaviour, which would force a spec delta and break
this change's `skip_specs: true` boundary. It belongs in P0 0.6 alongside the `generate` subcommand
decision. `-m tf_peek.main` is an internal path, but this is a test, not documentation.

### 5. Golden seeded from **current** output, paired with a strict-xfail defect ledger

`tests/integration/golden/` freezes today's output, warts included. `tests/integration/test_defects.py`
carries one `@pytest.mark.xfail(strict=True, reason="D<n>: …")` assertion per catalogued defect.

Consequences that make this the right trade:

- CI is green on day 1, so the harness merges on its own and P0 proceeds incrementally.
- Each fix in 0.1–0.5 produces a golden diff that *is* the reviewable change.
- `strict=True` means the day a fix lands and the marker is not removed, CI fails. The ledger
  cannot rot into a lie.
- The xfail list is the P0 checklist, executable and always current.

*Alternatives:* hand-write the target output (suite red until all of P0 lands; forces a big-bang
merge); snapshot with no ledger (defects never named in code, nothing detects a silent regression
of a defect no one asserted).

### 6. syrupy, configured to write readable `.md`

Five P0 changes rewrite the same attribute-diff table cell and P1 1.5 restructures it entirely, so
snapshot ergonomics matter more here than the dependency count suggests. syrupy provides
`--snapshot-update`, orphan-snapshot detection, and readable diffs.

**syrupy's default amber (`.ambr`) format must not be used.** The entire value of the golden is that
a reviewer reads its diff in a PR; a serialised blob defeats that. Use a single-file text extension
so each snapshot lands as a standalone `.md`. Exact extension subclassing is an implementation
detail for tasks.

*Alternative:* ~20 lines of `--update-golden` in `conftest.py`. Zero deps, but reimplements diff
rendering and orphan detection that syrupy already ships and tests.

### 7. One kitchen-sink fixture for the golden, focused fixtures per defect

`kitchen-sink.json` drives the golden and carries everything at once: sensitive values, nested
blocks, a pipe+newline value, nested `after_unknown`, `replace_paths`, `module_address`, and
`output_changes`. Focused fixtures (`sensitive.json`, `hostile-strings.json`, `nested-unknown.json`)
back the individual ledger assertions.

The split exists because a kitchen-sink golden has a known failure mode: fixing D3 also churns the
D1 rows, and reviewers stop reading. Assertions must fail for one nameable reason.

### 8. Fixtures are hand-written, cross-checked against the documented plan JSON format

A real `terraform show -json` capture would carry more authority but needs provider downloads and a
stack that does not exist. Hand-written fixtures must be checked against the format where it is
non-obvious — notably that `before_sensitive`/`after_sensitive` may be `bool`, `dict`, or `list`
(a whole resource can be `true`; nested lists appear as `[false, true, false]`), that `replace_paths`
mixes string keys and integer indices (`[["settings", 0, "tier"]]`), and that `after_unknown`
mirrors the value shape so a list-of-blocks unknown is `[{"ip": true}]`.

## Risks / Trade-offs

- **Fixtures encode the same mental model as the code they test** → validate the three shape rules
  in Decision 8 explicitly; treat any P0 fix that reveals a wrong fixture as a fixture bug first.
  This is the most likely way the harness is quietly wrong.
- **A committed golden contains `hunter2` labelled "expected"** → it is a fabricated value in a test
  fixture, and it is transient (0.1 removes it). Accepted, but the fixture must never use anything
  resembling a real credential.
- **tox tests the source tree, not the installed distribution** → verified: `tox -e py313` installs
  the `tf-peek` console script into `.tox/py313/bin/`, but `pytest.ini`'s `pythonpath = src` shadows
  the installed package, so `import tf_peek` resolves to `src/`. Determinism uses `-m tf_peek.main`,
  which needs only importability, so this change is unaffected. It does mean the packaged entry
  point is never exercised by tox — relevant to the deferred doc-invocation tests in 0.6. Accepted
  deliberately; see the `align-python-version-support` change.
- **tox now runs the integration suite on py311–py314** → first real multi-interpreter coverage of
  the CLI, so this is mostly upside; budget ~3.5 s per environment. Note `tox` is not invoked by any
  CI workflow, so this coverage is local-only until that changes.
- **The toolbox fork drifts further from `looztra/toolbox`** → the indirection is written in the
  upstream's own idiom so it can be pushed up later; not required by this change.
- **`--snapshot-update` makes it trivial to bless a regression** → the ledger is the counterweight;
  strict xfail fails on unexpected passes regardless of what the snapshot says.
- **Golden churn across P0** → expected and intended. If 1.5's restructuring proves unreviewable, a
  second snapshot of the Jinja2 render context (upstream of the template) can be added then; not
  worth the double maintenance at 336 LOC today.

## Migration Plan

1. Plumbing first, with a trivial placeholder integration test so `make integration-tests` is green
   and CI's stage stops lying. (Exit-5 constraint.)
2. Add syrupy, the single-file text extension, and the kitchen-sink fixture + golden.
3. Add the determinism subprocess test — expected to **fail**, since D2 is real. It is the one
   ledger entry that must be xfail from the start rather than after a snapshot.
4. Add the focused fixtures and the strict-xfail ledger for D1, D3, D4, D5.
5. Remove `allowlist_externals = bats` from `tox.ini`.

Rollback is `git revert`; nothing outside the repo is affected, and no runtime behaviour changes.

## Open Questions

- Should `IT_TESTS_TARGETS` be pushed upstream to `looztra/toolbox`? Does not affect this change —
  the fork works standalone either way.
- Should `tests/*.py` eventually move to `tests/unit/` for symmetry? Deliberately deferred; purely
  cosmetic and independently revertible.
- ~~`tox.ini` lists `py310` while `pyproject.toml` requires `>=3.11`, and `setenv PYTHONPATH`
  looks wrong.~~ **Resolved** — both are handled by the `align-python-version-support` change.
  `tox -e py310` fails hard (exit 2), so `make test-python-versions` is broken today; and the
  `setenv` is inert rather than wrong, since `pytest.ini` already provides `pythonpath = src`.
  Both changes edit `tox.ini`; if they land close together, expect a trivial merge.
