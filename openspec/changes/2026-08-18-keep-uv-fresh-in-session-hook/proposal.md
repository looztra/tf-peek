## Why

This supersedes `archive/2026-08-18-pin-exact-python-3.14-patch` (this branch's own prior commit,
not yet merged) after further investigation showed that change fixed the symptom at the wrong layer.

That earlier change pinned `.python-version` from the floating `3.14` to the exact `3.14.7`, reasoning
that `uv run`/`uv python install` resolve a floating minor version to whatever `3.14.x` is already
cached locally, and in one container that was a pre-release (`cpython-3.14.0rc2`) that trips a
documented CPython/pydantic regression (`pydantic/pydantic#12544`). That diagnosis was correct. The
fix was not: pinning the *project's* `.python-version` to an exact patch pushes permanent maintenance
onto every contributor and every CI run forever (bump it again for `3.14.8`, `3.14.9`, ... indefinitely)
to work around a problem that, on closer inspection, doesn't live in the project at all.

**Re-diagnosed, with proof**: the affected container's `uv` binary was `0.8.17`, dated `Mar 31` on
disk — baked into the container image at build time and never updated since. `uv`'s Python-download
catalog is bundled with the `uv` release itself, so a `uv` that old has never heard of the 3.14 GA
line; `uv python install 3.14.7` in that container failed outright with
`No download found for request: cpython-3.14.7-linux-x86_64-gnu`. This is a **stale tool in one
sandbox image**, not a floating-pin hazard in the project — `archive/2026-08-16-align-python-version-support`
already verified the same floating `3.14` pin resolves correctly to `3.14.7` elsewhere, and this
project's CI (which provisions its own toolchain per run) has never shown this failure.

**Proof the corrected fix works, from the same affected container, no project config change needed**:

```console
$ uv --version
uv 0.8.17
$ uv python install 3.14.7
error: No download found for request: cpython-3.14.7-linux-x86_64-gnu

$ pip install --user --upgrade uv   # the actual fix
$ uv --version
uv 0.12.5
$ uv python list | grep 3.14
cpython-3.14.7-linux-x86_64-gnu       <download available>
cpython-3.14.0rc2-linux-x86_64-gnu    /root/.local/share/uv/python/.../python3.14

$ uv python install 3.14   # .python-version, still floating, unchanged
Installed Python 3.14.7 in 3.79s

$ uv run pytest -q         # floating .python-version, upgraded uv, no repo change
83 passed in 6.91s
```

Upgrading only `uv` — leaving `.python-version` exactly as it was — turns the floating pin back into
what it was already meant to be: "whatever the current GA patch is," resolved correctly, with zero
ongoing maintenance for this repo.

## What Changes

- **Revert** `.python-version`: `3.14.7` → `3.14` (the floating pin, as it was before this branch's
  first commit). No exact-patch maintenance burden.
- **Delete** `archive/2026-08-18-pin-exact-python-3.14-patch` — this change replaces it outright; that
  directory's own explanation is now superseded by this one.
- The actual fix lands in `.claude/hooks/session-start.sh` (introduced by the sibling
  `2026-08-18-fail-on-critical-gate`/hook change on `claude/studies-analysis-openspec-0ljg4u`, PR #100):
  the SessionStart hook now also runs `pip install --user --upgrade uv` and pre-warms
  `uv python install "$(cat .python-version)"` once per Claude Code on the web session, before any
  project command runs. This is a **session-environment fix**, scoped to where the actual staleness
  lives, not a project-wide config change — regular CI and contributors' own machines were never
  affected and are untouched by this.
- **Dependency note**: this branch does not itself contain the hook change (that lives on PR #100's
  branch). This proposal documents the corrected diagnosis and the project-side half of the fix (the
  revert); the hook itself should be reviewed as part of PR #100. If PR #100 merges first, this branch
  rebases cleanly onto it; if this branch merges first, PR #100's hook commit still applies unchanged.

## Capabilities

None. Interpreter pin and session tooling only — same category as
`archive/2026-08-16-align-python-version-support` and the change this replaces;
`.openspec.yaml` sets `skip_specs: true` for the same reason.

## Impact

- **Files (this branch)**: `.python-version` (revert to one line), this `openspec/changes/` directory
  replacing the deleted one.
- **Files (PR #100, cross-referenced, not part of this branch's diff)**:
  `.claude/hooks/session-start.sh`.
- **CI**: unaffected either way — CI provisions its own toolchain per run and was never observed
  hitting this failure.
- **Local dev**: unaffected — a contributor's own `uv` is whatever they've installed, not the stale
  container-baked one this fix targets.
