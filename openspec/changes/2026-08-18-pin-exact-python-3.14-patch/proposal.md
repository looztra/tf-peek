## Why

`archive/2026-08-16-align-python-version-support` set `.python-version` to the floating minor
version `3.14` and verified all four target interpreters ("py311: OK ... py314: OK (Python 3.14.7,
35 passed)") against it. Two days later, `uv run pytest` in a different container reproduced a hard
collection failure on every test that imports `tf_peek.config`:

```console
$ uv run pytest tests/test_config.py -q
Using CPython 3.14.0rc2
...
E   TypeError: _eval_type() got an unexpected keyword argument 'prefer_fwd_module'
...
AssertionError
```

**Root cause, confirmed by direct reproduction, not just by reading the traceback:**

1. `uv python list` in the affected container shows only `cpython-3.14.0rc2-...` installed for the
   `3.14` line — a pre-release build, not the `3.14.7` the archived change tested against. `uv python
   install 3.14.7` in that same container fails outright: `error: No download found for request:
   cpython-3.14.7-linux-x86_64-gnu` — its local `uv` (0.8.17) has a stale/incomplete Python-download
   catalog that never learned about the 3.14 GA line, only the rc.
2. `.python-version` containing the bare `3.14` is a *floating* pin: `uv run`/`uv python install`
   resolve it to whatever `3.14.x` is already available locally before considering a download, so a
   container whose cached catalog stops at a pre-release silently runs the project against that
   pre-release instead of erroring or fetching the real release.
3. The failure itself is a documented, real regression: pydantic's `_typing_extra.py` calls the
   private CPython function `typing._eval_type()` with a `prefer_fwd_module` keyword that Python
   3.14's pre-release builds' `typing` module did not yet accept — see
   [pydantic/pydantic#12544](https://github.com/pydantic/pydantic/issues/12544) and the related
   CPython-side regression [python/cpython#136316](https://github.com/python/cpython/issues/136316)
   (fixed on the CPython side via a 3.14 patch backport). `typing._eval_type` is a private,
   underscore-prefixed API with no stability guarantee between an rc and the final release — exactly
   the kind of drift a pre-release build is expected to hit.
4. **Confirmed not a tf-peek or pydantic bug on a real interpreter**: the identical test suite passes
   cleanly (83 tests) under `uv run --python 3.13 pytest -q` with no code changes, and the archived
   change's own log already shows it passing under the real `3.14.7`. The failure is fully isolated
   to "this specific container's `uv` never downloaded true 3.14 GA and silently substituted an rc
   because the pin didn't say which patch."

Pinning the exact patch turns this from a silent, confusing failure (a three-layers-deep pydantic
`AssertionError` with no mention of "wrong Python version" anywhere in the trace) into either correct
behavior (any environment whose `uv` catalog actually has `3.14.7` available) or a plainly diagnosable
one (`error: No interpreter found for Python 3.14.7 in managed installations or search path` —
verified by making this exact edit in the affected container and re-running `uv run pytest`).

## What Changes

- `.python-version`: `3.14` → `3.14.7` — the exact patch already verified in
  `archive/2026-08-16-align-python-version-support`. `uv run`/`uv python install` (used by every
  workflow in `.github/workflows/code-checks.yaml` and `publish_docs.yaml`, none of which pass an
  explicit version) now resolve to that patch specifically rather than "whichever `3.14.x` happens to
  already be cached."
- Nothing else. `tox.ini`'s `envlist` factor `py314` is deliberately left as-is: tox's `py3NN` factor
  naming has no exact-patch form, and tox's own interpreter discovery is a separate mechanism from
  `.python-version` — not implicated in the reproduction above, so not touched here (avoids an
  unrelated edit to a file another recent change (`integration-test-harness`) already has active
  content in).
- No dependency version changes. `pydantic` is not pinned tighter or looser here — the current
  `pydantic>=2.12.5` already works correctly against the real `3.14.7`; this change addresses which
  interpreter gets selected, not which library version is installed.

## Capabilities

None. Build configuration / interpreter pin only, exactly like the change this follows up on;
`.openspec.yaml` sets `skip_specs: true` for the same reason that one did.

## Impact

- **Files**: `.python-version` (one line).
- **CI**: no change in behavior for any workflow that already resolves to a real `3.14.x` GA release
  (i.e. every currently-green CI run) — the exact pin matches what was already being selected there.
  The only behavior change is in an environment whose local `uv` Python catalog is stuck on a
  pre-release: it now fails fast with a clear "no interpreter found" message instead of silently
  running against a build with a known, documented regression.
- **Local dev**: a contributor whose machine has never run `uv python install` for 3.14 will have `uv`
  fetch `3.14.7` specifically on first `uv run`, same as today's floating pin would (assuming a
  non-stale `uv` catalog).
