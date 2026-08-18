## 1. Fix

- [x] 1.1 Change `.python-version` from `3.14` to `3.14.7`.

## 2. Verification

- [x] 2.1 Reproduced the failure first: `uv run pytest tests/test_config.py -q` against the floating
      `3.14` pin, in a container whose `uv` Python catalog only had `cpython-3.14.0rc2` cached,
      produced `TypeError: _eval_type() got an unexpected keyword argument 'prefer_fwd_module'` →
      `AssertionError` during collection.
- [x] 2.2 Confirmed the same container's `uv` cannot fetch true 3.14 GA at all:
      `uv python install 3.14.7` → `error: No download found for request:
      cpython-3.14.7-linux-x86_64-gnu` (a stale/incomplete local Python-download catalog, not a repo
      problem).
- [x] 2.3 Confirmed the suite is unaffected by the underlying interpreter bug on a real, unaffected
      build: `uv run --python 3.13 pytest -q` → 83 passed, `uv run --python 3.13 ruff check .` → all
      checks passed.
- [x] 2.4 After the pin edit, re-ran `uv run pytest tests/test_config.py -q` in the same affected
      container: now fails fast and clearly with
      `error: No interpreter found for Python 3.14.7 in managed installations or search path`,
      instead of the cryptic pydantic internals crash — confirms the fix changes the failure mode
      from silent-and-confusing to explicit-and-actionable in a broken environment, without needing
      that specific container to be able to download 3.14.7 itself.
- [ ] 2.5 On a CI runner / any environment with a current `uv` Python catalog (e.g. GitHub Actions,
      which re-provisions `uv` fresh per run — see `.github/workflows/code-checks.yaml`'s
      `uv python install` steps): confirm `uv run pytest` resolves `3.14.7` and the full suite passes,
      matching `archive/2026-08-16-align-python-version-support`'s original verification. Not
      reproducible from this container; verify via the PR's own CI run.
